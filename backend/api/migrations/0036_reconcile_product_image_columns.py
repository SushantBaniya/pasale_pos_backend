from django.db import migrations


def reconcile_product_image_columns(apps, schema_editor):
    table_name = "api_product"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor,
                table_name,
            )
        }

        quoted_table = connection.ops.quote_name(table_name)

        if "product_Img" in existing_columns:
            quoted_column = connection.ops.quote_name("product_Img")
            cursor.execute(
                f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}"
            )

        if "image_url" not in existing_columns:
            quoted_column = connection.ops.quote_name("image_url")
            cursor.execute(
                f"ALTER TABLE {quoted_table} "
                f"ADD COLUMN {quoted_column} varchar(200) NULL"
            )

        if "image_public_id" not in existing_columns:
            quoted_column = connection.ops.quote_name("image_public_id")
            cursor.execute(
                f"ALTER TABLE {quoted_table} "
                f"ADD COLUMN {quoted_column} varchar(255) NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0035_remove_product_product_img_product_image_public_id_and_more"),
    ]

    operations = [
        migrations.RunPython(
            reconcile_product_image_columns,
            migrations.RunPython.noop,
        ),
    ]
