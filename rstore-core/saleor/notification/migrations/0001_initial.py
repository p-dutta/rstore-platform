# Generated by Django 3.0.6 on 2020-09-20 08:25

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import saleor.core.utils.json_serializer


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('private_metadata', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, encoder=saleor.core.utils.json_serializer.CustomJsonEncoder, null=True)),
                ('metadata', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, encoder=saleor.core.utils.json_serializer.CustomJsonEncoder, null=True)),
                ('title', models.CharField(max_length=100)),
                ('message', models.CharField(max_length=250)),
                ('target_url', models.URLField(max_length=255)),
                ('send_to_all', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'notification',
                'verbose_name_plural': 'notifications',
                'ordering': ('created',),
                'permissions': (('manage_notifications', 'Manage notifications.'),),
            },
        ),
        migrations.CreateModel(
            name='Segment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('segment_id', models.CharField(max_length=100, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'segment',
                'verbose_name_plural': 'segments',
                'ordering': ('created',),
                'permissions': (('manage_notifications', 'Manage notifications.'),),
            },
        ),
    ]
