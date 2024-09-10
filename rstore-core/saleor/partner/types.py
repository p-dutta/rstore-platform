import graphene
from graphene import relay

from ...partner import models
from ..core.connection import CountableDjangoObjectType
from ..core.types import Image


class Partner(CountableDjangoObjectType):

    logo = graphene.Field(Image, size=graphene.Int(description="Partner logo"))

    class Meta:
        description = "Represents partners data."
        interfaces = [relay.Node]
        model = models.Partner

    @staticmethod
    def resolve_logo(root: models.Partner, info, size=None, **_kwargs):
        if root.logo:
            return Image.get_adjusted(
                image=root.logo,
                alt=None,
                size=size,
                rendition_key_set="partners",
                info=info,
            )
