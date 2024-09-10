# Generated by Django 3.0.6 on 2020-09-02 06:53

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import versatileimagefield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('account', '0052_auto_20200831_0713'),
    ]

    operations = [
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('partner_name', models.CharField(max_length=255)),
                ('partner_oidc_id', models.CharField(max_length=63, unique=True)),
                ('partner_id', models.CharField(max_length=255, unique=True)),
                ('call_center_number', models.CharField(blank=True, max_length=11, validators=[django.core.validators.RegexValidator(code='wrong_phone', message='Please give correct phone number like 01811111111', regex='^01[3-9][0-9]{8}$')])),
                ('email', models.EmailField(max_length=254, null=True, unique=True)),
                ('description', models.TextField(blank=True, default='', null=True)),
                ('enabled', models.BooleanField(default=False)),
                ('consent_required', models.BooleanField(default=True)),
                ('standard_flow_enabled', models.BooleanField(default=False)),
                ('direct_access_grant_enabled', models.BooleanField(default=False)),
                ('implicit_flow_enabled', models.BooleanField(default=False)),
                ('full_scope_allowed', models.BooleanField(default=False)),
                ('root_url', models.URLField(blank=True, null=True)),
                ('default_scopes', models.TextField(null=True)),
                ('access_type', models.CharField(max_length=15)),
                ('service_account_enabled', models.BooleanField(default=False)),
                ('redirect_urls', models.TextField(null=True)),
                ('secret', models.CharField(max_length=63, unique=True)),
                ('logo', versatileimagefield.fields.VersatileImageField(blank=True, null=True, upload_to='partner-logos')),
                ('address', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='partner_addresses', to='account.Address')),
            ],
        ),
    ]
