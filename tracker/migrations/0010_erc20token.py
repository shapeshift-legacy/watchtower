# Generated by Django 2.0.7 on 2018-09-27 06:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0009_auto_20180907_0156'),
    ]

    operations = [
        migrations.CreateModel(
            name='ERC20Token',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contract_address', models.CharField(max_length=255)),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('symbol', models.CharField(blank=True, max_length=100, null=True)),
                ('precision', models.IntegerField()),
            ],
        ),
    ]