from django.db import migrations, models


DEFAULT_LABELS = [
    "FADED_KERB",
    "VEGETATION_GROWTH_ON_SHOULDERS",
    "GAP_IN_MEDIAN_VEGETATION",
    "ENCROACHMENT",
    "DAMAGED_ATTENUATORS",
    "DAMAGED_ANTI_GLARE",
    "DAMAGED_RUMBLE_STRIPS",
    "DAMAGED_ROAD_STUDS",
    "DAMAGED_BUS_SHELTER",
    "MISSING_COVER_SLABS_OVER_DRAIN",
    "DAMAGED_FOOTPATH",
    "FADED_CONCRETE_BARRIER",
    "DAMAGED_COVER_SLABS_OVER_DRAIN",
    "DAMAGED_METAL_BEAM_CRASH_BARRIER",
    "DAMAGED_POLES",
    "DAMAGED_PEDESTRIAN_GUARD_RAIL",
    "FADED_GUARD_RAIL",
    "DAMAGED_SIGN_STRUCTURES_VMS",
    "DAMAGED_BARRICADING",
    "UNAUTHORIZED_SIGN_BOARDS",
    "DAMAGED_SOLAR_BLINKER",
    "UNAUTHORIZED_MEDIAN_OPENING",
    "FADED_BOUNDARY_STONE",
    "MISSING_STUDS",
    "OBSTRUCTED_SIGN",
    "VEGETATION_SIGN",
    "BLOCKED_DRAINAGE",
    "DAMAGED_CONCRETE_BARRIER",
    "VEGETATION_OBSTRUCTION_AT_POSTS",
    "DAMAGED_R_O_W_PILLAR",
    "FADED_ZEBRA_CROSSING",
    "VEGETATION_MBCB",
    "DAMAGED_SPEED_BREAKER",
    "DAMAGED_DELINATORS",
    "FADED_DIAGONAL_MARKING",
    "FADED_CHEVRON_MARKING",
    "FADED_ARROW_MARKING",
    "KERB_VIOLATION",
    "DAMAGED_GUARD_POSTS",
    "FADED_SIGN",
    "DAMAGED_KERB",
    "VEGETATION_KERB",
    "DAMAGED_SIGN",
    "BLOCKED_KERB_DRAINAGE",
    "FADED_EDGE_MARKING",
    "FADED_LANE_MARKING",
    "MINOR_LONGITUDINAL_CRACK",
    "MAJOR_LONGITUDINAL_CRACK",
    "SPALLING",
    "SHOVING",
    "SURFACE_DELAMINATION",
    "BLOCK_CRACK",
    "PAVER_BLOCK",
    "PATCH",
    "MANHOLE",
    "MUD",
    "BLEEDINGEDGE_CRACK",
    "REFLECTION_CRACK",
    "TRANSVERSE_CRACK",
    "SLIPPAGE",
    "MAJOR_POTHOLE",
    "MINOR_POTHOLE",
    "RAVELLING",
    "CORNER_CRACK",
    "DIAGONAL_CRACK",
    "GARBAGE",
    "ALLIGATOR_CRACK",
    "RUTTING",
    "EDGE_DROP",
    "DUST",
    "WATER_LOGGING",
]


def forwards_merge_labels(apps, schema_editor):
    Label = apps.get_model("accounts", "Label")

    canonical_by_name = {}
    duplicate_ids = []

    for label in Label.objects.select_related("project").order_by("id"):
        cleaned_name = (label.name or "").strip()
        if not cleaned_name:
            duplicate_ids.append(label.id)
            continue

        lookup_key = cleaned_name.lower()
        canonical = canonical_by_name.get(lookup_key)
        if canonical is None:
            label.name = cleaned_name
            label.save(update_fields=["name"])
            label.projects_multi.add(label.project_id)
            canonical_by_name[lookup_key] = label
            continue

        canonical.projects_multi.add(label.project_id)
        duplicate_ids.append(label.id)

    if duplicate_ids:
        Label.objects.filter(id__in=duplicate_ids).delete()


def forwards_seed_default_labels(apps, schema_editor):
    Label = apps.get_model("accounts", "Label")
    for name in DEFAULT_LABELS:
        Label.objects.get_or_create(name=name, defaults={"color": "#FF5733"})


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_remove_unused_annotation_scaffolding"),
    ]

    operations = [
        migrations.AddField(
            model_name="label",
            name="projects_multi",
            field=models.ManyToManyField(blank=True, related_name="labels_multi_temp", to="accounts.project"),
        ),
        migrations.RunPython(forwards_merge_labels, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="label",
            name="uniq_label_name_per_project",
        ),
        migrations.RemoveField(
            model_name="label",
            name="project",
        ),
        migrations.RenameField(
            model_name="label",
            old_name="projects_multi",
            new_name="projects",
        ),
        migrations.AlterField(
            model_name="label",
            name="projects",
            field=models.ManyToManyField(blank=True, related_name="labels", to="accounts.project"),
        ),
        migrations.AlterField(
            model_name="label",
            name="name",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.RunPython(forwards_seed_default_labels, migrations.RunPython.noop),
    ]
