# Generated by Django 2.0.7 on 2020-02-01 20:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0030_auto_20191211_1601'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountBalance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('network', models.CharField(choices=[('BTC', 'BTC'), ('BCH', 'BCH'), ('LTC', 'LTC'), ('DOGE', 'DOGE'), ('DASH', 'DASH'), ('DGB', 'DGB'), ('ETH', 'ETH'), ('ATOM', 'ATOM')], max_length=100)),
                ('symbol', models.CharField(max_length=100)),
                ('address', models.CharField(max_length=255)),
                ('identifier', models.CharField(max_length=255)),
                ('balance_type', models.CharField(default='R', max_length=10)),
                ('balance', models.DecimalField(decimal_places=0, max_digits=78)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracker.Account')),
            ],
        ),
        migrations.AddField(
            model_name='erc20token',
            name='supported',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterUniqueTogether(
            name='accountbalance',
            unique_together={('network', 'address', 'identifier', 'balance_type')},
        ),
        migrations.RunSQL(
            """
                update tracker_erc20token
                set supported = true
                where lower(contract_address) in (
                lower('0xc770EEfAd204B5180dF6a14Ee197D99d808ee52d'),
                lower('0xa74476443119A942dE498590Fe1f2454d7D4aC0d'),
                lower('0x6810e776880c02933d47db1b9fc05908e5386b96'),
                lower('0xaec2e87e0a235266d9c5adc9deb4b2e29b54d009'),
                lower('0x888666CA69E0f178DED6D75b5726Cee99A87D698'),
                lower('0xe0b7927c4af23765cb51314a0e0521a9645f0e2a'),
                lower('0xec67005c4E498Ec7f55E092bd1d35cbC47C91892'),
                lower('0x1985365e9f78359a9B6AD760e32412f4a445E862'),
                lower('0xb9e7f8568e08d5659f5d29c4997173d84cdf2607'),
                lower('0x667088b212ce3d06a1b553a7221E1fD19000d9aF'),
                lower('0xcb94be6f13a1182e4a4b6140cb7bf2025d28e41b'),
                lower('0x607F4C5BB672230e8672085532f7e901544a7375'),
                lower('0x960b236A07cf122663c4303350609A66A7B288C0'),
                lower('0x0d8775f648430679a709e98d2b0cb6250d2887ef'),
                lower('0x1f573d6fb3f13d689ff844b4ce37794d79a7ff1c'),
                lower('0x744d70fdbe2ba4cf95131626614a1763df805b9e'),
                lower('0x1776e1f26f98b1a5df9cd347953a26dd3cb46671'),
                lower('0x08711d3b02c8758f2fb3ab4e80228418a7f8e39c'),
                lower('0x41e5560054824ea6b0732e656e3ad64e20e94e45'),
                lower('0xF433089366899D83a9f26A773D59ec7eCF30355e'),
                lower('0xB97048628DB6B661D4C2aA833e95Dbe1A905B280'),
                lower('0x419d0d8bdd9af5e606ae2232ed285aff190e711b'),
                lower('0x0abdace70d3790235af448c88547603b945604ea'),
                lower('0xe41d2489571d322189246dafa5ebde1f4699f498'),
                lower('0xaf30d2a7e90d7dc361c8c4585e9bb7d2f6f15bc7'),
                lower('0xd26114cd6EE289AccF82350c8d8487fedB8A0C07'),
                lower('0x4156D3342D5c385a87D264F90653733592000581'),
                lower('0xf970b8e36e23f7fc3fd752eea86f8be8d83375a6'),
                lower('0xb64ef51c888972c908cfacf59b47c1afbc0ab8ac'),
                lower('0xB8c77482e45F1F44dE1745F52C74426C631bDD52'),
                lower('0xdac17f958d2ee523a2206206994597c13d831ec7'),
                lower('0x9992ec3cf6a55b00978cddf2b27bc6882d88d1ec'),
                lower('0x05f4a42e251f2d52b8ed15e9fedaacfcef1fad27'),
                lower('0x0f5d2fb29fb7d3cfee444a200298f468908cc942'),
                lower('0xc5bbae50781be1669306b9e001eff57a2957b09d'),
                lower('0xfa1a856cfa3409cfa145fa4e20eb270df3eb21ab'),
                lower('0xbf2179859fc6d5bee9bf9158632dc51678a4100e'),
                lower('0x0000000000085d4780B73119b644AE5ecd22b376'),
                lower('0x5ca9a71b1d01849c0a95490cc00559717fcf0d1d'),
                lower('0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2'),
                lower('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'),
                lower('0x42d6622dece394b54999fbd73d108123806f6a18'),
                lower('0xb63b606ac810a52cca15e44bb630fd42d8d1d83d'),
                lower('0xd4fa1460f537bb9085d22c7bccb5dd450ef28e3a'),
                lower('0x8e870d67f660d95d5be530380d0ec0bd388289e1'),
                lower('0x514910771af9ca656af840dff83e8264ecf986ca'),
                lower('0xdd974d5c2e2928dea5f71b9825b8b646686bd200'),
                lower('0x039b5649a59967e3e936d7471f9c3700100ee1ab'));
            """
        )
    ]
