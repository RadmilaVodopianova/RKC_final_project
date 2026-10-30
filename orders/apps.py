from django.apps import AppConfig
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models.signals import post_save, pre_save


class OrdersConfig(AppConfig):
    name = 'orders'
    verbose_name = "Заявки"

    def ready(self):
        order_model = self.get_model("Order")
        pre_save.connect(
            _remember_order_status,
            sender=order_model,
            dispatch_uid="orders.remember_email_status",
        )
        post_save.connect(
            _queue_order_status_email,
            sender=order_model,
            dispatch_uid="orders.queue_status_email",
        )


def _remember_order_status(sender, instance, raw, using, update_fields, **kwargs):
    instance._email_previous_status = None
    if raw or not instance.pk:
        return
    if update_fields is not None and "status" not in update_fields:
        return
    instance._email_previous_status = (
        sender.objects.using(using).filter(pk=instance.pk)
        .values_list("status", flat=True).first()
    )


def _queue_order_status_email(sender, instance, created, raw, using, update_fields, **kwargs):
    previous_status = getattr(instance, "_email_previous_status", None)
    if raw or created or previous_status is None:
        return
    if update_fields is not None and "status" not in update_fields:
        return
    saved_order = sender.objects.using(using).values(
        "pk", "customer_number", "full_name", "email", "status",
    ).get(pk=instance.pk)
    if saved_order["status"] == previous_status:
        return
    saved_order["status_display"] = dict(sender.Status.choices).get(
        saved_order["status"], saved_order["status"],
    )
    transaction.on_commit(
        lambda order_data=saved_order: _send_order_status_email(order_data),
        using=using,
        robust=True,
    )


def _send_order_status_email(order_data):
    descriptions = {
        "new": "Заявка має статус «Нова» та очікує опрацювання.",
        "processing": "Заявку взято в обробку. Менеджер уточнює деталі.",
        "confirmed": "Заявку погоджено. Деталі отримання уточнюйте у менеджера.",
        "completed": "Заявку позначено як виконану.",
        "cancelled": "Заявку скасовано. Якщо маєте запитання, зверніться до менеджера.",
    }
    lines = [
        f"Вітаємо, {order_data['full_name']}!",
        "",
        f"Статус вашої заявки №{order_data['customer_number']} змінено.",
        f"Поточний статус: {order_data['status_display']}.",
        descriptions.get(order_data["status"], "Деталі уточнюйте у менеджера."),
        "",
        f"Для зв’язку з менеджером: {settings.MANAGER_EMAIL}",
        "Роздільнянський ковбасний цех",
    ]
    EmailMessage(
        subject=f"Оновлення заявки №{order_data['customer_number']}: {order_data['status_display']}",
        body="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order_data["email"]],
        reply_to=[settings.MANAGER_EMAIL],
    ).send(using="default")
