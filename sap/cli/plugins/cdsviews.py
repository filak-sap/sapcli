"""Non common CDS operations"""

import sap.cli.core
from sap.adt.datapreview import DataPreview

class CdsViewsPlugin(sap.cli.plugin.APluginBaseADT):

    def command_group(self):
        return CommandGroup()


class CommandGroup(sap.cli.core.CommandGroup):
    """Container for user commands."""

    def __init__(self):
        super().__init__('cdsviews')


@CommandGroup.argument('name', type=str)
@CommandGroup.command('exportinterface')
# pylint: disable=unused-argument
def exportinterface(connection, args):
    """export public interface"""

    cdsname = args.name.upper()

    sqlconsole = DataPreview(connection)

    fields = sqlconsole.execute(f"SELECT field_name_up, data_type, data_type_length FROM vdmcdsmdfield WHERE cds_entity_name_up = '{cdsname}'", rows=99999)
    associations = sqlconsole.execute(f"SELECT association_name_up, target_entity_name_up FROM vdmcdsmdassoc WHERE cds_entity_name_up = '{cdsname}'", rows=99999)

    for field in fields:
        print(field['FIELD_NAME_UP'], field['DATA_TYPE'], field['DATA_TYPE_LENGTH'])

    for assoc in associations:
        print(assoc['ASSOCIATION_NAME_UP'], )

    return 0


@CommandGroup.argument('--end', type=str, default='20231130000000')
@CommandGroup.argument('--start', type=str, default='20230614000000')
@CommandGroup.command('exemptions')
# pylint: disable=unused-argument
def cone_exemptions(connection, args):
    sqlconsole = DataPreview(connection)

    query = f"""SELECT DISTINCT exempt~pgmid, exempt~object, exempt~obj_name
      FROM CRMCHKEXC as exempt
      INNER JOIN  VDMCDS_MD_DDLSLIFECYCLESTSC1 as cdsc1
      ON cdsc1~ddls_name = exempt~obj_name
      WHERE exempt~chkid in ( 'ARS_CMP', 'ANDP', 'DATD', 'DEPR', 'DPR2', 'DPR4' )
        AND cdsc1~lifecycle_status = 'RELEASED'
        AND exempt~agreed = '3'
        AND exempt~agrtstamp >= '{args.start}'
        AND exempt~agrtstamp <= '{args.end}'"""

    rows = sqlconsole.execute(query, rows=1000000)
    for row in rows:
        print(row['OBJ_NAME'])
