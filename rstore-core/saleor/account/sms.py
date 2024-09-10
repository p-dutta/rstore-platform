from saleor.core import sms_manager
from saleor.settings import TEMPLATE_ROOT
from ..celeryconf import app
import os.path


def _get_full_path(path):
    return os.path.join(TEMPLATE_ROOT, path)


INITIAL_SUBMISSION_TEMPLATE = _get_full_path("templated_sms/account/initial_submission.sms")
NOTIFY_DCO_TEMPLATE = _get_full_path("templated_sms/account/notify_dco.sms")
INITIAL_FORM_APPROVE_TEMPLATE = _get_full_path("templated_sms/account/approve_initial.sms")
KYC_SUBMISSION_TEMPLATE = _get_full_path("templated_sms/account/kyc_submission.sms")
NOTIFY_CM_TEMPLATE = _get_full_path("templated_sms/account/notify_cm.sms")
KYC_FORM_APPROVE_TEMPLATE = _get_full_path("templated_sms/account/approve_kyc.sms")
KYC_FORM_REJECT_TEMPLATE = _get_full_path("templated_sms/account/reject.sms")


def _send_sms(to, message):
    if sms_manager.can_send():
        sms_manager.send_sms(to, message)


@app.task
def send_initial_submission_sms(to):
    file = open(INITIAL_SUBMISSION_TEMPLATE, "r")
    _send_sms(to, file.read())


@app.task
def send_notification_dco_sms(to, agent_name, domain):
    file = open(NOTIFY_DCO_TEMPLATE, "r")
    message = file.read().format(agent_name=agent_name, domain=domain)
    _send_sms(to, message)


@app.task
def send_initial_approval_sms(to, domain):
    file = open(INITIAL_FORM_APPROVE_TEMPLATE, "r")
    message = file.read().format(domain=domain)
    _send_sms(to, message)


@app.task
def send_kyc_submission_sms(to):
    file = open(KYC_SUBMISSION_TEMPLATE, "r")
    _send_sms(to, file.read())


@app.task
def send_notification_cm_sms(to, agent_name, domain):
    file = open(NOTIFY_CM_TEMPLATE, "r")
    message = file.read().format(agent_name=agent_name, domain=domain)
    _send_sms(to, message)


@app.task
def send_kyc_approval_sms(to, domain):
    file = open(KYC_FORM_APPROVE_TEMPLATE, "r")
    message = file.read().format(domain=domain)
    _send_sms(to, message)


@app.task
def send_rejection_sms(to, reason):
    file = open(KYC_FORM_REJECT_TEMPLATE, "r")
    message = file.read().format(reason=reason)
    _send_sms(to, message)
