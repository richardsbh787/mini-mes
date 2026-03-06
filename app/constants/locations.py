# app/constants/locations.py

SUPPLIER = "SUPPLIER"

RM_STORE = "RM_STORE"

KIT_PARK = "KIT_PARK"      # RM/SFG staged for line pickup
LINE = "LINE"              # material physically at production line

PRODUCTION = "PRODUCTION"  # consumed / in-process (logical sink)

WIP = "WIP"                # WIP storage / between departments
PACK_PARK = "PACK_PARK"    # FG finished but awaiting transfer to warehouse (warehouse full / manpower issue)

FG_STORE = "FG_STORE"      # warehouse FG location
CUSTOMER = "CUSTOMER"      # shipped out

ALL = {
    SUPPLIER,
    RM_STORE,
    KIT_PARK,
    LINE,
    PRODUCTION,
    WIP,
    PACK_PARK,
    FG_STORE,
    CUSTOMER,
}