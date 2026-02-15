"""
Admin configuration for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    """Inline para Profile no admin de User."""

    model = Profile
    can_delete = False
    verbose_name = "Perfil"
    verbose_name_plural = "Perfil"
    fk_name = "user"
    filter_horizontal = ["unidades"]
    readonly_fields = ["id", "criado_em", "atualizado_em"]

    fieldsets = (
        ("Informações do Perfil", {"fields": ("role", "unidades", "ativo")}),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )


class UserAdmin(BaseUserAdmin):
    """Customiza o admin de User para incluir Profile."""

    inlines = [ProfileInline]
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "get_role",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "profile__role"]

    def get_role(self, obj):
        """Retorna o papel do usuário."""
        try:
            return obj.profile.get_role_display()
        except Profile.DoesNotExist:
            return "-"

    get_role.short_description = "Papel"


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin para o modelo Profile."""

    list_display = ["user", "role", "ativo", "criado_em"]
    list_filter = ["role", "ativo", "criado_em"]
    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    filter_horizontal = ["unidades"]
    readonly_fields = ["id", "criado_em", "atualizado_em"]

    fieldsets = (
        ("Usuário", {"fields": ("user",)}),
        ("Informações do Perfil", {"fields": ("role", "unidades", "ativo")}),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )
