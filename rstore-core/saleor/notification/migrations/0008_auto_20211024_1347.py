# Generated by Django 3.0.6 on 2021-10-24 13:47

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0007_auto_20211017_1304'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notification',
            name='recipient',
        ),
        migrations.AddField(
            model_name='notification',
            name='recipients',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict),
        ),
    ]
