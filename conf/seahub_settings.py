# -*- coding: utf-8 -*-
SECRET_KEY = "fu3aj()-gkv(vzs0h-+be09y6jfy*sb7k*v-jv)f_^5rbg)#cj"
FILE_SERVER_ROOT = "http://localhost/seafhttp"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'seahub-db',
        'USER': 'seafile',
        'PASSWORD': 'seafile',
        'HOST': '10.0.0.203',
        'PORT': '3306'
    }
}

# Enable Office Online Server
#ENABLE_OFFICE_WEB_APP = True

MULTI_INSTITUTION = True
EXTRA_MIDDLEWARE_CLASSES = (
    'seahub.institutions.middleware.InstitutionMiddleware',
)

ENABLE_TOW_FACTOR_AUTH = True

TWO_FACTOR_SMS_GATEWAY = 'seahub.two_factor.gateways.onewaysms.Onewaysms'
#TWO_FACTOR_SMS_GATEWAY = 'seahub.two_factor.gateways.fake.Fake'

ENABLE_STORAGE_CLASSES = True
#STORAGE_CLASS_MAPPING_POLICY = 'USER_SELECT'
#STORAGE_CLASS_MAPPING_POLICY = 'REPO_ID_MAPPING'
STORAGE_CLASS_MAPPING_POLICY = 'ROLE_BASED'

ENABLED_ROLE_PERMISSIONS = {
    'default': {
        'can_add_repo': True,
        'can_add_group': True,
        'can_add_public_repo': True,
        'can_view_org': True,
        'can_use_global_address_book': True,
        'can_generate_share_link': True,
        'can_generate_upload_link': True,
        'can_invite_guest': True,
        'can_connect_with_android_clients': True,
        'can_connect_with_ios_clients': True,
        'can_connect_with_desktop_clients': True,
        'storage_ids': [ 'default_storage' ],
    },
     'customerauser': {
        'can_add_group': True,
        'can_add_public_repo': True,
        'can_add_repo': True,
        'can_connect_with_android_clients': True,
        'can_connect_with_desktop_clients': True,
        'can_connect_with_ios_clients': True,
        'can_drag_drop_folder_to_sync': True,
        'can_export_files_via_mobile_client': True,
        'can_generate_share_link': True,
        'can_generate_upload_link': True,
        'can_invite_guest': False,
        'can_publish_repo': False,
        'can_send_share_link_mail': False,
        'can_use_global_address_book': False,
        'can_use_wiki': False,
        'can_view_org': False,
        #'role_quota': '10g',
    'storage_ids': [ 'customera_storage'],
},
   'customerbuser': {
        'can_add_group': True,
        'can_add_public_repo': True,
        'can_add_repo': True,
        'can_connect_with_android_clients': True,
        'can_connect_with_desktop_clients': True,
        'can_connect_with_ios_clients': True,
        'can_drag_drop_folder_to_sync': True,
        'can_export_files_via_mobile_client': True,
        'can_generate_share_link': True,
        'can_generate_upload_link': True,
        'can_invite_guest': False,
        'can_publish_repo': False,
        'can_send_share_link_mail': False,
        'can_use_global_address_book': False,
        'can_use_wiki': False,
        'can_view_org': False,
        #'role_quota': '',
        'storage_ids': [ 'customerb_storage'],
},

}
