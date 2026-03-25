PRODUCT_CACHE_TIMEOUT = 300  # 5 minutes
TOPUP_CACHE_TIMEOUT = 300 
NOTIFICATION_CACHE_TIMEOUT = 300
CATEGORY_CACHE_TIMEOUT = 300
TAG_CACHE_TIMEOUT = 300
PACKAGE_CACHE_TIMEOUT = 300
PRODUCT_LIST_CACHE_PAGE_KEY_PREFIX = "product_list_cache_page_"
PRODUCT_ADMIN_LIST_CACHE_PAGE_KEY_PREFIX = "product_admin_list_cache_page_"
TOPUP_GAME_PUBLIC_CACHE_KEY_PREFIX = "topup_game_public"
TOPUP_GAME_ADMIN_CACHE_KEY_PREFIX = "topup_game_admin"
TOPUP_GAME_LIST_PUBLIC_CACHE_KEY_PREFIX = "topup_game_list_public_"
TOPUP_GAME_LIST_ADMIN_CACHE_KEY_PREFIX = "topup_game_list_admin"
TOPUP_GAME_PACKAGE_LIST_CACHE_KEY_PREFIX = "topup_game_package_list_"
TOPUP_GAME_PACKAGE_LIST_ADMIN_CACHE_KEY_PREFIX = "topup_game_package_list_admin_"
NOTIFICATION_CACHE_KEY_PREFIX = "notification_user_"
NOTIFICATION_ADMIN_CACHE_KEY_PREFIX = "notification_admin"
NOTIFICATIONS_CACHE_KEY_PREFIX = "notifications_all_user_"
NOTIFICATIONS_LIST_CACHE_KEY_PREFIX = "notifications_all_"
NOTIFICATIONS_ALL_ADMIN_CACHE_KEY_PREFIX = "notifications_all_admin"

# catalog cache
def get_product_cache_timeout():
    return PRODUCT_CACHE_TIMEOUT

def format_filter_value(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, str) and v.lower() in ("true", "false"):
        return v.capitalize()
    return v

def get_product_list_cache_page_key(
    page_number,
    page_size,
    filter_params=None,
    search_query=None,
    is_admin=False,
    extra=None
):
    key = f"{PRODUCT_LIST_CACHE_PAGE_KEY_PREFIX if not is_admin else PRODUCT_ADMIN_LIST_CACHE_PAGE_KEY_PREFIX}{page_number}_size_{page_size}"
    if filter_params:
        key += f"_filter_{filter_params}"
    if search_query:
        key += f"_search_{search_query}"
    if extra:
        key += f"_{extra}"
    return key

def get_product_cache_key(slug):
    return f"product_cache_{slug}"

# topup cache
def get_topup_game_cache_key(slug, is_admin=False):
    prefix = TOPUP_GAME_ADMIN_CACHE_KEY_PREFIX if is_admin else TOPUP_GAME_PUBLIC_CACHE_KEY_PREFIX
    return f"{prefix}_{slug}"

def get_topup_cache_timeout():
    return TOPUP_CACHE_TIMEOUT

def get_topup_game_list_public_cache_key():
    return f"{TOPUP_GAME_LIST_PUBLIC_CACHE_KEY_PREFIX}"

def get_topup_game_list_search_cache_key(
    page_number,
    page_size,
    filter_params=None,
    search_query=None,
    is_admin=False,
    extra=None
):
    key = f"{TOPUP_GAME_LIST_PUBLIC_CACHE_KEY_PREFIX if not is_admin else TOPUP_GAME_LIST_ADMIN_CACHE_KEY_PREFIX}{page_number}_size_{page_size}"
    if filter_params:
        key += f"_filter_{filter_params}"
    if search_query:
        key += f"_search_{search_query}"
    if extra:
        key += f"_{extra}"
    return key

def get_topup_game_list_admin_cache_key():
    return f"{TOPUP_GAME_LIST_ADMIN_CACHE_KEY_PREFIX}"

def get_packages_cache_timeout():
    return PACKAGE_CACHE_TIMEOUT

def get_topup_package_list_cache_page_key(
    page_number,
    page_size,
    ordering=None,
    currency="USD",
    is_admin=False
):
    key = f"{TOPUP_GAME_PACKAGE_LIST_CACHE_KEY_PREFIX if not is_admin else TOPUP_GAME_PACKAGE_LIST_ADMIN_CACHE_KEY_PREFIX}{page_number}_size_{page_size}"
    if ordering:
        key += f"_ordering_{ordering}"
    if currency:
        key += f"_currency_{currency}"
    return key

# notification cache
def get_notification_list_cache_page_key(
    page_number,
    page_size,
    filter_params=None,
    search_query=None
):
    key = f"{NOTIFICATIONS_LIST_CACHE_KEY_PREFIX}{page_number}_size_{page_size}"
    if filter_params:
        key += f"_filter_{filter_params}"
    if search_query:
        key += f"_search_{search_query}"
    return key

def get_notification_cache_key(notification_id, user):
    if user.is_superuser:
        return f"{NOTIFICATION_ADMIN_CACHE_KEY_PREFIX}{notification_id}"
    return f"{NOTIFICATION_CACHE_KEY_PREFIX}{user.id}_{notification_id}"

def get_notifications_cache_key(user):
    if user.is_superuser:
        return f"{NOTIFICATIONS_ALL_ADMIN_CACHE_KEY_PREFIX}"
    return f"{NOTIFICATIONS_CACHE_KEY_PREFIX}{user.id}"

def get_notification_cache_timeout():
    return NOTIFICATION_CACHE_TIMEOUT

# tag

def get_tag_cache_timeout():
    return TAG_CACHE_TIMEOUT

# category
def get_category_cache_timeout():
    return CATEGORY_CACHE_TIMEOUT

def get_category_cache_key(slug):
    return f"category_cache_{slug}"
