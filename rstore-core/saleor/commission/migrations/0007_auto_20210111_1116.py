# Generated by Django 3.0.6 on 2021-01-11 05:16

import django.contrib.postgres.fields.jsonb
from django.db import migrations
import saleor.core.utils.json_serializer


class Migration(migrations.Migration):

    dependencies = [
        ('commission', '0006_rulehistory_rule'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='commission',
            name='rules',
        ),
        migrations.AddField(
            model_name='commission',
            name='rules',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict, encoder=saleor.core.utils.json_serializer.CustomJsonEncoder),
        ),
    ]
