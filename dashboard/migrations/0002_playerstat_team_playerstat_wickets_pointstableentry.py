from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerstat",
            name="team",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="playerstat",
            name="wickets",
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name="PointsTableEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("team", models.CharField(max_length=100, unique=True)),
                ("played", models.IntegerField(default=0)),
                ("won", models.IntegerField(default=0)),
                ("lost", models.IntegerField(default=0)),
                ("tied", models.IntegerField(default=0)),
                ("no_result", models.IntegerField(default=0)),
                ("points", models.IntegerField(default=0)),
                ("net_run_rate", models.FloatField(default=0)),
            ],
            options={
                "ordering": ["-points", "-net_run_rate", "team"],
            },
        ),
    ]
