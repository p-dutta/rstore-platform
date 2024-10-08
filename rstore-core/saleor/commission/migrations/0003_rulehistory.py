# Generated by Django 3.0.6 on 2020-12-30 15:47

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import saleor.core.utils.json_serializer


class Migration(migrations.Migration):

    dependencies = [
        ('commission', '0002_auto_20201227_1407'),
    ]

    operations = [
        migrations.CreateModel(
            name='RuleHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_rule', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, encoder=saleor.core.utils.json_serializer.CustomJsonEncoder, null=True)),
                ('engine_rule', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, encoder=saleor.core.utils.json_serializer.CustomJsonEncoder, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-updated',),
                'permissions': (('manage_rules', 'Manage rules'),),
            },
        ),
    ]
