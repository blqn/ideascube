# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-10-13 09:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ideascube', '0011_auto_20161007_1220'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='current_occupation',
            field=models.CharField(blank=True, choices=[('student', 'Student'), ('teacher', 'Teacher'), ('no_profession', 'Without profession'), ('profit_profession', 'Profit profession'), ('volunteering', 'Volunteering'), ('other', 'Other')], max_length=32, verbose_name='Current occupation'),
        ),
    ]
