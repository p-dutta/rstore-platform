import graphene
from datetime import datetime
from django.db import IntegrityError
from .input_types import CreateRuleInput
from ..enums import CommissionCategoryEnum, CommissionTypeEnum
from ...core.mutations import ModelMutation, ModelDeleteMutation
from ...core.types.common import RuleError
from ....core.permissions import RulePermissions
from ....commission import models
from ....product.models import ProductVariant
from django.core.exceptions import ValidationError
from ....commission.error_codes import RuleErrorCode
from ....commission.commission_recalculation import recalculate_commission_on_rule_update,\
    recalculate_commission_on_rule_delete


def gen_dictionary(name, operator, value):
    return {"name": name, "operator": operator, "value": value}


def validate_input(data):
    _validate_required(data, "service", "Service")
    _validate_required(data, "timeline", "Timeline information")

    timeline = data.get("timeline")
    if timeline.get("use_timeline"):
        _validate_required(timeline, "start_date", "Start date")
        _validate_required(timeline, "end_date", "End date")

        timeline["start_date"] = str(timeline.get("start_date"))
        timeline["end_date"] = str(timeline.get("end_date"))

    _validate_required(data, "target", "Target information")

    target = data.get("target")
    if target.get("target_by_profile"):
        _validate_required(target, "profile", "User profile")
        _validate_user_profile(target)

    if target.get("target_by_geography"):
        _validate_required(target, "geography", "Geographical information")

        geography = target.get("geography")
        districts = geography.get("districts")
        thanas = geography.get("thanas")

        if not districts and not thanas:
            _validate_required({}, "districts", "District or Thana")

        district_ids = []
        for district_global in districts:
            try:
                _model, dist_pk = graphene.Node.from_global_id(district_global)
                district_ids.append(dist_pk)
            except Exception:
                raise ValidationError(
                    {
                        "districts": ValidationError(
                            "Please provide valid District IDs",
                            code=RuleErrorCode.INVALID
                        )
                    }
                )
        geography["district_ids"] = district_ids

        if thanas:
            thana_ids = []
            for thana_global in thanas:
                try:
                    _model, th_pk = graphene.Node.from_global_id(thana_global)
                    thana_ids.append(th_pk)
                except Exception:
                    raise ValidationError(
                        {
                            "thanas": ValidationError(
                                "Please provide valid Thana IDs",
                                code=RuleErrorCode.INVALID
                            )
                        }
                    )
            geography["thana_ids"] = thana_ids

    if target.get("target_by_group"):
        _validate_required(target, "group", "Group information")
        group = target.get("group")
        _validate_required(group, "name", "Group name")
        _validate_required(group, "users", "Group user list")
        user_ids = []
        for group_u_id in group["users"]:
            try:
                _model, u_pk = graphene.Node.from_global_id(group_u_id)
                user_ids.append(u_pk)
            except Exception:
                raise ValidationError(
                    {
                        "group_users": ValidationError(
                            "Please provide valid User IDs",
                            code=RuleErrorCode.INVALID
                        )
                    }
                )
        group["user_ids"] = user_ids

    _validate_required(data, "calculation", "Calculation information")

    calculation = data.get("calculation")
    _validate_required(calculation, "commission_type", "Commission type")
    _validate_required(calculation, "commission_category", "Commission category")

    commission_category = calculation.get("commission_category")
    if commission_category == CommissionCategoryEnum.FIXED:
        _validate_required(calculation, "fixed", "Fixed commission information")

        fixed = calculation.get("fixed")
        _validate_required(fixed, "commission", "Commission value")
        _validate_required(fixed, "max_cap", "Max cap value")

    if commission_category == CommissionCategoryEnum.RANGE:
        _validate_required(calculation, "range", "Range information")
        ranges = calculation.get("range")
        i = 0
        while i < len(ranges):
            range_item = ranges[i]
            _validate_required(range_item, "min", "Min value")
            _validate_required(range_item, "max", "Max value")
            _validate_required(range_item, "commission", "Commission value")
            _validate_required(range_item, "max_cap", "Max cap value")
            if range_item["max"] <= range_item["min"]:
                raise ValidationError(
                    {
                        "max": ValidationError(
                            "Max value can not be less than min value",
                            code=RuleErrorCode.INVALID
                        )
                    }
                )
            if i > 0:
                prev_range_item = ranges[i - 1]
                if range_item["min"] <= prev_range_item["max"]:
                    raise ValidationError(
                        {
                            "min": ValidationError(
                                "Min value can not be less than previous item's max value",
                                code=RuleErrorCode.INVALID
                            )
                        }
                    )
            i += 1

    if commission_category == CommissionCategoryEnum.PRODUCT:
        _validate_required(calculation, "product", "Product information")
        products = calculation.get("product")
        for product in products:
            _validate_required(product, "product_sku", "Product SKU value")
            _validate_required(product, "commission", "Commission value")
            _validate_required(product, "max_cap", "Max cap value")
            if not ProductVariant.objects.filter(sku=product["product_sku"]).exists():
                raise ValidationError(
                    {
                        "product_sku": ValidationError(
                            "Invalid product sku",
                            code=RuleErrorCode.INVALID
                        )
                    }
                )

    _validate_required(calculation, "vat_ait", "VAT/AIT")

    return data


def _validate_required(data, key, name):
    if data.get(key) is None:
        raise ValidationError(
            {
                key: ValidationError(
                    f"{name} is required",
                    code=RuleErrorCode.REQUIRED
                )
            }
        )


def _validate_user_profile(target):
    profile = target.get("profile")
    try:
        _profile = models.UserProfile.objects.get(name=profile)
    except Exception:
        raise ValidationError(
            {
                "profile": ValidationError(
                    "Please provide valid User Profile",
                    code=RuleErrorCode.INVALID
                )
            }
        )


def gen_root_all_cond(data):
    root_all_cond = []
    service = gen_dictionary("service", "equal_to", data["service"])
    root_all_cond.append(service)

    timeline = data.get("timeline")
    if timeline["use_timeline"]:
        start_date = datetime.strptime(timeline["start_date"], "%Y-%m-%d")
        end_date_time = datetime.strptime(timeline["end_date"] + " 23:59:59", "%Y-%m-%d %H:%M:%S")
        start_date_unix = datetime.timestamp(start_date)
        end_date_unix = datetime.timestamp(end_date_time)

        timeline_start = gen_dictionary("timeline", "greater_than_or_equal_to", start_date_unix)
        timeline_end = gen_dictionary("timeline", "less_than_or_equal_to", end_date_unix)
        root_all_cond.append(timeline_start)
        root_all_cond.append(timeline_end)

    target = data.get("target")
    if target.get("target_by_profile"):
        profile = gen_dictionary("profile", "equal_to", target["profile"])
        root_all_cond.append(profile)

    if target.get("target_by_geography"):
        geography = target.get("geography")
        districts = gen_dictionary("district", "shares_at_least_one_element_with", geography["district_ids"])
        list_geography = [districts]
        if geography.get("thana_ids"):
            thanas = gen_dictionary("thana", "shares_at_least_one_element_with", geography["thana_ids"])
            list_geography.append(thanas)

        any_geography = {"any": list_geography}
        root_all_cond.append(any_geography)

    if target.get("target_by_group"):
        group = target["group"]
        all_group = gen_dictionary(group["name"], "is_contained_by", group["user_ids"])
        root_all_cond.append(all_group)
    return root_all_cond


def generate_rule(rule_id, data):
    client_rule = {}
    engine_rule = []

    calculation = data["calculation"]

    root_all_cond = gen_root_all_cond(data)
    if calculation["commission_category"] == CommissionCategoryEnum.FIXED:
        all_cond = {"all": root_all_cond}

        fixed = calculation["fixed"]
        vat_ait = calculation["vat_ait"]
        actions = []
        action_params = {
            "commission": fixed.get("commission"),
            "max_cap": fixed.get("max_cap"),
            "rule_id": rule_id,
            "vat_ait": vat_ait
        }
        action_name = "calculate_commission_absolute" if calculation["commission_type"] == CommissionTypeEnum.ABSOLUTE \
            else "calculate_commission_percentage"
        action = {"name": action_name, "params": action_params}
        actions.append(action)

        root_dict = {"conditions": all_cond, "actions": actions}
        engine_rule.append(root_dict)

    elif calculation["commission_category"] == CommissionCategoryEnum.RANGE:
        ranges = calculation["range"]
        vat_ait = calculation["vat_ait"]
        for range_item in ranges:
            range_cond = []
            range_cond.extend(root_all_cond)
            min_cond = gen_dictionary("transaction", "greater_than_or_equal_to", range_item["min"])
            max_cond = gen_dictionary("transaction", "less_than_or_equal_to", range_item["max"])
            range_cond.append(min_cond)
            range_cond.append(max_cond)
            all_cond = {"all": range_cond}

            range_actions = []
            action_params = {
                "commission": range_item["commission"],
                "max_cap": range_item["max_cap"],
                "rule_id": rule_id,
                "vat_ait": vat_ait
            }
            action_name = "calculate_commission_absolute" if calculation[
                                                                 "commission_type"] == CommissionTypeEnum.ABSOLUTE \
                else "calculate_commission_percentage"
            action = {"name": action_name, "params": action_params}
            range_actions.append(action)
            range_dict = {"conditions": all_cond, "actions": range_actions}
            engine_rule.append(range_dict)

    elif calculation["commission_category"] == CommissionCategoryEnum.PRODUCT:
        products = calculation["product"]
        vat_ait = calculation["vat_ait"]
        for product_item in products:
            product_cond = []
            product_cond.extend(root_all_cond)
            sku_cond = gen_dictionary("product_sku", "contains", product_item["product_sku"])
            product_cond.append(sku_cond)
            all_cond = {"all": product_cond}

            product_actions = []
            action_params = {
                "commission": product_item["commission"],
                "max_cap": product_item["max_cap"],
                "rule_id": rule_id,
                "vat_ait": vat_ait,
                "product_sku": product_item["product_sku"]
            }
            action_name = "calculate_commission_absolute_product" if calculation[
                                                                         "commission_type"] == CommissionTypeEnum.ABSOLUTE \
                else "calculate_commission_percentage_product"
            action = {"name": action_name, "params": action_params}
            product_actions.append(action)
            product_dict = {"conditions": all_cond, "actions": product_actions}
            engine_rule.append(product_dict)

    client_rule.update({"name": data["name"]})
    client_rule.update({"service": data["service"]})
    client_rule.update({"timeline": data["timeline"]})

    target = data["target"]
    user_dict = {}
    user_dict.update({"target_by_all": target.get("target_by_all", False)})
    user_dict.update({"target_by_profile": target.get("target_by_profile", False)})
    user_dict.update({"target_by_geography": target.get("target_by_geography", False)})
    user_dict.update({"target_by_group": target.get("target_by_group", False)})
    if target.get("target_by_profile"):
        user_dict.update({"profile": target["profile"]})
    if target.get("target_by_geography"):
        target["geography"].pop("district_ids", None)
        target["geography"].pop("thana_ids", None)
        user_dict.update({"geography": target["geography"]})
    if target.get("target_by_group"):
        target["group"].pop("user_ids")
        user_dict.update({"group": target["group"]})

    client_rule.update({"user": user_dict})
    client_rule.update({"calculation": data["calculation"]})

    return client_rule, engine_rule


class CreateRule(ModelMutation):
    class Arguments:
        input = CreateRuleInput(
            description="Fields required to create the rule.",
            required=True,
        )

    class Meta:
        description = "Creates a particular rule by it's name."
        model = models.Rule
        permissions = (RulePermissions.MANAGE_RULES,)
        error_type_class = RuleError
        error_type_field = "rule_errors"

    @classmethod
    def clean_input(cls, info, instance, data, **kwargs):
        data = super().clean_input(info, instance, data)
        validated_data = validate_input(data)
        name = data['name']
        rule_with_name_exists = models.Rule.objects.filter(name__iexact=name).exists()
        if rule_with_name_exists:
            raise ValidationError(
                {
                    "name": ValidationError(
                        "Rule with this name already exists",
                        code=RuleErrorCode.INVALID
                    )
                }
            )
        return validated_data

    @classmethod
    def save(cls, info, instance, cleaned_input):

        instance.name = cleaned_input["name"]
        instance.type = cleaned_input["type"]
        instance.category = cleaned_input["category"]
        instance.commission_category = cleaned_input["calculation"]["commission_category"]
        instance.is_active = True
        instance.save()

        client_rule, engine_rule = generate_rule(instance.pk, cleaned_input)

        rule_history = models.RuleHistory(rule=instance, client_rule=client_rule, engine_rule=engine_rule)
        rule_history.save()


class UpdateRule(ModelMutation):
    class Arguments:
        id = graphene.ID(description="ID of a rule to update.", required=True)
        input = CreateRuleInput(
            description="Fields required to create the rule.",
            required=True,
        )

    class Meta:
        description = "Creates a particular rule by it's name."
        model = models.Rule
        permissions = (RulePermissions.MANAGE_RULES,)
        error_type_class = RuleError
        error_type_field = "rule_errors"

    @classmethod
    def clean_input(cls, info, instance, data, **kwargs):
        data = super().clean_input(info, instance, data)
        validated_data = validate_input(data)
        return validated_data

    @staticmethod
    def gen_dictionary(name, operator, value):
        return {"name": name, "operator": operator, "value": value}

    @classmethod
    def save(cls, info, instance, cleaned_input):
        try:
            if_timeline = cleaned_input["timeline"]["use_timeline"]
            start_date = None
            end_date = None
            if if_timeline:
                start_date = cleaned_input["timeline"]["start_date"]
                end_date = cleaned_input["timeline"]["end_date"]
            instance.name = cleaned_input["name"]
            instance.type = cleaned_input["type"]
            instance.category = cleaned_input["category"]
            instance.commission_category = cleaned_input["calculation"]["commission_category"]
            if cleaned_input.get("is_active", None) is not None:
                instance.is_active = cleaned_input["is_active"]
            else:
                instance.is_active = True
            instance.save()

            client_rule, engine_rule = generate_rule(instance.pk, cleaned_input)

            rule_history = models.RuleHistory(rule=instance, client_rule=client_rule, engine_rule=engine_rule)
            rule_history.save()

            if instance.is_active:
                recalculate_commission_on_rule_update.delay(
                    instance.pk, if_timeline, start_date, end_date
                )

        except IntegrityError as e:
            if 'unique constraint' in e.args[0]:
                raise ValidationError(
                    {
                        "name": ValidationError(
                            "Rule with this name already exists",
                            code=RuleErrorCode.INVALID
                        )
                    }
                )


class RuleDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(description="ID of a rule to delete.", required=True)
        delete_commission = graphene.Boolean(
            description="Flag to determine whether to delete respective commissions",
            default_value=False, required=True
        )

    class Meta:
        description = "Deletes a rule."
        model = models.Rule
        permissions = (RulePermissions.MANAGE_RULES,)
        error_type_class = RuleError
        error_type_field = "rule_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        try:
            rule = cls.get_node_or_error(info, data.get("id"))
        except Exception:
            raise ValidationError(
                {
                    "id": ValidationError(
                        "No Rule found with this ID",
                        code=RuleErrorCode.NOT_FOUND
                    )
                }
            )
        _validate_required(data, "delete_commission", "Delete Commission")

        rule_history_ids = rule.get_rule_histories_pk_list()

        rule.delete()

        if data.get("delete_commission"):
            recalculate_commission_on_rule_delete.delay(rule_history_ids)

        return cls.success_response(rule)
