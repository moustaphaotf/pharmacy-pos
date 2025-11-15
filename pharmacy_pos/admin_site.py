"""
Admin site personnalisé pour afficher le dashboard par défaut.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.urls import path

User = get_user_model()


class CustomAdminSite(admin.AdminSite):
    site_header = "La Pharmacie de la Poste"
    site_title = "Pharmacie de la Poste"
    index_title = "Dashboard"

    def index(self, request, extra_context=None):
        """
        Surcharge l'index de l'admin pour afficher le dashboard si l'utilisateur a les permissions.
        Sinon, affiche la page d'accueil admin normale.
        """
        extra_context = extra_context or {}
        
        # Vérifier si l'utilisateur peut voir le dashboard
        user_role = getattr(request.user, 'role', None)
        can_view_dashboard = user_role in [User.Roles.ADMIN, User.Roles.PHARMACIST] if user_role else False
        
        if can_view_dashboard:
            # Afficher le dashboard
            context = {
                **self.each_context(request),
                **extra_context,
                'can_view_financial': user_role == User.Roles.ADMIN,
                'can_view_products': user_role in [User.Roles.ADMIN, User.Roles.PHARMACIST],
                'user': request.user,
                'title': 'Dashboard',
            }
            return render(request, 'admin/index.html', context)
        else:
            # Afficher la page d'accueil admin normale
            return super().index(request, extra_context)

