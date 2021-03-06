# Generated by Django 2.0.7 on 2018-08-11 00:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessedBlock',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('block_height', models.IntegerField()),
                ('block_hash', models.CharField(max_length=500)),
                ('block_time', models.DateTimeField()),
                ('processed_at', models.DateTimeField(auto_now_add=True)),
                ('previous_hash', models.CharField(max_length=500)),
                ('previous_block', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tracker.ProcessedBlock')),
            ],
        ),
    ]
