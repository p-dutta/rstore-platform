import os

import graphene
from typing import List, Dict

from . import NotificationType
from .models import Notification
from ..account.models import User
from ..celeryconf import app
from datetime import datetime

from ..target.models import Target, AttributeTargetSales, PartnerTargetSales


@app.task
def notify_for_general_target(message, notification_type: NotificationType, target_pk: int):
    target_user = Target.objects.get(pk=target_pk).user_id
    Notification.objects.create_notification(
        type=notification_type,
        message=message,
        path=os.path.join("targets", graphene.Node.to_global_id("Target", target_pk)),
        recipients=[target_user]
    )


@app.task
def notify_for_attribute_target(message, notification_type: NotificationType, attribute_target_ids: List[int]):
    for at_id in attribute_target_ids:
        attribute_target = AttributeTargetSales.objects.get(pk=at_id)
        target_user = attribute_target.target_user.user_id
        Notification.objects.create_notification(
            type=notification_type,
            message=message,
            path=os.path.join("attribute-targets", graphene.Node.to_global_id("AttributeTargetSales", at_id)),
            recipients=[target_user]
        )


@app.task
def notify_for_partner_target(message, notification_type: NotificationType, partner_target_ids: List[int]):
    for pt_id in partner_target_ids:
        partner_target = PartnerTargetSales.objects.get(pk=pt_id)
        target_user = partner_target.target_user.user_id
        Notification.objects.create_notification(
            message=message,
            type=notification_type,
            path=os.path.join("partner-targets", graphene.Node.to_global_id("PartnerTargetSales", pt_id)),
            recipients=[target_user]
        )


@app.task
def notify_on_registration_and_kyc(
        message, notification_type: NotificationType, user_request_pk: int, recipient_id: int
):
    Notification.objects.create_notification(
        message=message,
        type=notification_type,
        path=os.path.join(
            "agent-requests-detail",
            graphene.Node.to_global_id("UserRequest", user_request_pk)
        ),
        recipients=[recipient_id]
    )


@app.task
def notify_on_registration_processed(message, notification_type: NotificationType, user_pk: int):
    agent = User.objects.get(id=user_pk)
    agent_region = agent.regions.first()

    dcm = User.objects.get_dcm_by_region(agent_region)

    if notification_type == NotificationType.AGENT_REQUEST_PROCESSED:
        cm = User.objects.get_cm_by_region(agent_region)
        Notification.objects.create_notification(
            message=message,
            type=notification_type,
            path=os.path.join(
                "staff",
                graphene.Node.to_global_id("User", user_pk)
            ),
            recipients=[cm.pk, dcm.pk]
        )
    elif notification_type == NotificationType.KYC_PROCESSED:
        dco = User.objects.get_dco_by_region(agent_region)
        Notification.objects.create_notification(
            message=message,
            type=notification_type,
            path=os.path.join(
                "staff",
                graphene.Node.to_global_id("User", user_pk)
            ),
            recipients=[dco.pk, dcm.pk]
        )
