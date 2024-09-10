import graphene
from ...partner import models


def resolve_partners():
    return models.Partner.objects.all()


def resolve_partner(partner_id):
    _model, partner_pk = graphene.Node.from_global_id(partner_id)
    return models.Partner.objects.get(id=partner_pk)
