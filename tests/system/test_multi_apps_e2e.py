from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from src.application.outbox_publisher import OutboxPublisher
from src.application.task_service import TaskLifecycleService
from src.core.constants import TaskStatus
from src.domain.entities import DLQEntry, Queue
from src.domain.task_registry import global_task_registry
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.session import session_scope
from src.worker.runtime import WorkerRuntime


@pytest.mark.asyncio
async def test_app1_notification_service_pipeline() -> None:
    notif_queue = f"notif-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=notif_queue, broker_backend="native")
        )

    @global_task_registry.task(name=f"send_email_{notif_queue}", queue=notif_queue, priority=5)
    async def send_email(recipient: str, template: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "delivered": True,
            "message_id": f"msg-{uuid4().hex[:8]}",
            "recipient": recipient,
            "template": template,
            "sent_at": datetime.now(UTC).isoformat(),
        }

    @global_task_registry.task(name=f"send_sms_{notif_queue}", queue=notif_queue, priority=1)
    async def send_sms(phone: str, text: str) -> dict[str, Any]:
        return {
            "sent": True,
            "provider": "twilio",
            "phone": phone,
            "segments": 1,
        }

    task_service = TaskLifecycleService()
    email_task = await task_service.submit_task(
        task_type=f"send_email_{notif_queue}",
        payload={
            "recipient": "user@example.com",
            "template": "welcome_email",
            "context": {"name": "Alice"},
        },
        queue=notif_queue,
        tenant_id="tenant-notifications-app",
        priority=5,
    )
    sms_task = await task_service.submit_task(
        task_type=f"send_sms_{notif_queue}",
        payload={"phone": "+15551234567", "text": "Your security code is 482910"},
        queue=notif_queue,
        tenant_id="tenant-notifications-app",
        priority=1,
    )

    assert email_task.status == TaskStatus.PENDING
    assert sms_task.status == TaskStatus.PENDING

    publisher = OutboxPublisher(batch_size=50)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"notif-worker-{uuid4().hex[:6]}",
        queues=[notif_queue],
        concurrency=4,
    )

    messages = await worker.broker.consume(
        queue=notif_queue, worker_id=worker.worker_id, batch_size=2
    )
    assert len(messages) == 2

    for msg in messages:
        await worker._process_message(msg)

    final_email = await task_service.get_task(email_task.task_id)
    final_sms = await task_service.get_task(sms_task.task_id)

    assert final_email is not None
    assert final_email.status == TaskStatus.SUCCEEDED
    assert final_email.result["delivered"] is True
    assert final_email.result["recipient"] == "user@example.com"

    assert final_sms is not None
    assert final_sms.status == TaskStatus.SUCCEEDED
    assert final_sms.result["sent"] is True
    assert final_sms.result["phone"] == "+15551234567"


@pytest.mark.asyncio
async def test_app2_billing_and_payment_gateway() -> None:
    pay_queue = f"pay-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=pay_queue, broker_backend="native")
        )

    @global_task_registry.task(name=f"process_payment_{pay_queue}", queue=pay_queue)
    async def process_payment(account_id: str, amount: float, currency: str) -> dict[str, Any]:
        if amount > 10000.0:
            raise ValueError("Transaction flagged as potential fraud")
        return {
            "status": "SETTLED",
            "account_id": account_id,
            "charge_id": f"ch_{uuid4().hex[:12]}",
            "amount": amount,
            "currency": currency,
        }

    task_service = TaskLifecycleService()
    payment_key = f"pay-idem-{uuid4().hex}"

    task_v1 = await task_service.submit_task(
        task_type=f"process_payment_{pay_queue}",
        payload={"account_id": "acct_9876", "amount": 149.99, "currency": "USD"},
        queue=pay_queue,
        tenant_id="tenant-billing-app",
        idempotency_key=payment_key,
    )

    task_v2 = await task_service.submit_task(
        task_type=f"process_payment_{pay_queue}",
        payload={"account_id": "acct_9876", "amount": 149.99, "currency": "USD"},
        queue=pay_queue,
        tenant_id="tenant-billing-app",
        idempotency_key=payment_key,
    )

    assert task_v1.task_id == task_v2.task_id

    publisher = OutboxPublisher(batch_size=50)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"pay-worker-{uuid4().hex[:6]}",
        queues=[pay_queue],
        concurrency=2,
    )
    messages = await worker.broker.consume(
        queue=pay_queue, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1
    await worker._process_message(messages[0])

    completed_charge = await task_service.get_task(task_v1.task_id)
    assert completed_charge is not None
    assert completed_charge.status == TaskStatus.SUCCEEDED
    assert completed_charge.result["status"] == "SETTLED"
    assert completed_charge.result["amount"] == 149.99

    fraud_task = await task_service.submit_task(
        task_type=f"process_payment_{pay_queue}",
        payload={"account_id": "acct_suspicious", "amount": 999999.0, "currency": "USD"},
        queue=pay_queue,
        tenant_id="tenant-billing-app",
        max_attempts=1,
    )
    await publisher.publish_batch()

    fraud_messages = await worker.broker.consume(
        queue=pay_queue, worker_id=worker.worker_id, batch_size=1
    )
    assert len(fraud_messages) == 1
    await worker._process_message(fraud_messages[0])

    failed_fraud = await task_service.get_task(fraud_task.task_id)
    assert failed_fraud is not None
    assert failed_fraud.status == TaskStatus.FAILED

    async with session_scope() as session:
        dlq_repo = DLQRepository(session)
        dlq_entry = await dlq_repo.create_entry(
            DLQEntry(
                task_id=fraud_task.task_id,
                tenant_id="tenant-billing-app",
                reason="Transaction flagged as potential fraud",
                error_class="ValueError",
            )
        )
        assert dlq_entry.task_id == fraud_task.task_id


@pytest.mark.asyncio
async def test_app3_analytics_and_report_generator() -> None:
    rep_queue = f"rep-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=rep_queue, broker_backend="native")
        )

    @global_task_registry.task(name=f"generate_kpi_report_{rep_queue}", queue=rep_queue)
    async def generate_kpi_report(metric_group: str, period: str) -> dict[str, Any]:
        return {
            "report_id": f"rep-{uuid4().hex[:8]}",
            "metric_group": metric_group,
            "period": period,
            "records_processed": 450000,
            "download_url": f"https://cdn.example.com/reports/{uuid4().hex}.pdf",
            "checksum": uuid4().hex,
        }

    task_service = TaskLifecycleService()

    active_report_task = await task_service.submit_task(
        task_type=f"generate_kpi_report_{rep_queue}",
        payload={"metric_group": "monthly_revenue", "period": "2026-Q3"},
        queue=rep_queue,
        tenant_id="tenant-analytics-app",
    )

    obsolete_report_task = await task_service.submit_task(
        task_type=f"generate_kpi_report_{rep_queue}",
        payload={"metric_group": "monthly_revenue", "period": "2026-Q2-DRAFT"},
        queue=rep_queue,
        tenant_id="tenant-analytics-app",
    )

    cancelled_report = await task_service.cancel_task(
        obsolete_report_task.task_id, reason="Superseded by finalized quarter parameters"
    )
    assert cancelled_report.status == TaskStatus.CANCELLED

    publisher = OutboxPublisher(batch_size=50)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"report-worker-{uuid4().hex[:6]}",
        queues=[rep_queue],
        concurrency=2,
    )
    messages = await worker.broker.consume(
        queue=rep_queue, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1
    assert messages[0].envelope.task_id == active_report_task.task_id
    await worker._process_message(messages[0])

    completed_report = await task_service.get_task(active_report_task.task_id)
    assert completed_report is not None
    assert completed_report.status == TaskStatus.SUCCEEDED
    assert completed_report.result["records_processed"] == 450000
    assert "https://cdn.example.com" in completed_report.result["download_url"]
