"""
Configuration admin personnalisée pour utiliser CustomAdminSite.
"""

from django.contrib.admin.apps import AdminConfig


class CustomAdminConfig(AdminConfig):
    default_site = 'pharmacy_pos.admin_site.CustomAdminSite'

