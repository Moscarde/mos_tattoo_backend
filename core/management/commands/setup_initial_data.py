"""
Management command para criar dados iniciais do sistema.

Esta command cria:
- Grupos de usuários (ADMIN_TECNICO, GERENTE_GERAL, GERENTE_UNIDADE)
- Permissões associadas aos grupos
- Unidades iniciais
- Usuários de exemplo

A command é idempotente, podendo ser executada múltiplas vezes sem duplicar dados.
"""

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile, UserRole
from core.models import Unidade


class Command(BaseCommand):
    """Command para bootstrap de dados iniciais do sistema."""

    help = "Cria dados iniciais do sistema (grupos, permissões, unidades e usuários de exemplo)"

    def add_arguments(self, parser):
        """Adiciona argumentos opcionais à command."""
        parser.add_argument(
            "--skip-users",
            action="store_true",
            help="Pula a criação de usuários de exemplo",
        )

    def handle(self, *args, **options):
        """Executa a command."""
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Iniciando setup de dados iniciais..."))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        try:
            with transaction.atomic():
                # 1. Criar grupos
                self.stdout.write("\n[1/4] Criando grupos...")
                grupos = self._criar_grupos()

                # 2. Configurar permissões
                self.stdout.write("\n[2/4] Configurando permissões...")
                self._configurar_permissoes(grupos)

                # 3. Criar unidades
                self.stdout.write("\n[3/4] Criando unidades...")
                unidades = self._criar_unidades()

                # 4. Criar usuários de exemplo (se não foi solicitado para pular)
                if not options["skip_users"]:
                    self.stdout.write("\n[4/4] Criando usuários de exemplo...")
                    self._criar_usuarios(grupos, unidades)
                else:
                    self.stdout.write(
                        "\n[4/4] Pulando criação de usuários (--skip-users)"
                    )

                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(self.style.SUCCESS("✓ Setup concluído com sucesso!"))
                self.stdout.write(self.style.SUCCESS("=" * 60))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Erro durante o setup: {str(e)}"))
            raise

    def _criar_grupos(self):
        """Cria os grupos do sistema."""
        grupos = {}
        nomes_grupos = {
            "ADMIN_TECNICO": "Administrador Técnico",
            "GERENTE_GERAL": "Gerente Geral",
            "GERENTE_UNIDADE": "Gerente de Unidade",
        }

        for codigo, nome in nomes_grupos.items():
            grupo, created = Group.objects.get_or_create(name=codigo)
            grupos[codigo] = grupo

            if created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Grupo criado: {codigo}"))
            else:
                self.stdout.write(f"  - Grupo já existe: {codigo}")

        return grupos

    def _configurar_permissoes(self, grupos):
        """Configura permissões para os grupos."""
        # ADMIN_TECNICO: todas as permissões
        admin_tecnico = grupos["ADMIN_TECNICO"]
        todas_permissoes = Permission.objects.all()
        count_antes = admin_tecnico.permissions.count()
        admin_tecnico.permissions.set(todas_permissoes)
        count_depois = admin_tecnico.permissions.count()

        if count_depois > count_antes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Permissões configuradas para ADMIN_TECNICO: "
                    f"{count_depois} permissões"
                )
            )
        else:
            self.stdout.write(
                f"  - ADMIN_TECNICO já possui todas as permissões ({count_depois})"
            )

        # GERENTE_GERAL e GERENTE_UNIDADE: sem permissões de admin (apenas via API)
        for grupo_name in ["GERENTE_GERAL", "GERENTE_UNIDADE"]:
            grupo = grupos[grupo_name]
            grupo.permissions.clear()
            self.stdout.write(
                f"  - {grupo_name}: sem permissões de admin (acesso via API)"
            )

    def _criar_unidades(self):
        """Cria as unidades iniciais."""
        unidades_data = [
            {"nome": "São Paulo", "codigo": "SP-01"},
            {"nome": "Rio de Janeiro", "codigo": "RJ-01"},
            {"nome": "Belo Horizonte", "codigo": "BH-01"},
            {"nome": "Curitiba", "codigo": "CT-01"},
            {"nome": "Porto Alegre", "codigo": "POA-01"},
        ]

        unidades = {}
        for data in unidades_data:
            unidade, created = Unidade.objects.get_or_create(
                codigo=data["codigo"], defaults={"nome": data["nome"]}
            )
            unidades[data["codigo"]] = unidade

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Unidade criada: {unidade.codigo} - {unidade.nome}"
                    )
                )
            else:
                self.stdout.write(
                    f"  - Unidade já existe: {unidade.codigo} - {unidade.nome}"
                )

        return unidades

    def _criar_usuarios(self, grupos, unidades):
        """Cria usuários de exemplo."""
        usuarios_data = [
            {
                "username": "admin_tecnico",
                "email": "admin@example.com",
                "password": "admin123",
                "first_name": "Admin",
                "last_name": "Técnico",
                "is_staff": True,
                "is_superuser": True,
                "grupo": "ADMIN_TECNICO",
                "role": UserRole.ADMIN_TECNICO,
                "unidades": [],
            },
            {
                "username": "gerente_geral",
                "email": "gerente.geral@example.com",
                "password": "gerente123",
                "first_name": "Gerente",
                "last_name": "Geral",
                "is_staff": False,
                "is_superuser": False,
                "grupo": "GERENTE_GERAL",
                "role": UserRole.GERENTE_GERAL,
                "unidades": [],
            },
            {
                "username": "gerente_unidade_sp",
                "email": "gerente.sp@example.com",
                "password": "gerente123",
                "first_name": "Gerente",
                "last_name": "São Paulo",
                "is_staff": False,
                "is_superuser": False,
                "grupo": "GERENTE_UNIDADE",
                "role": UserRole.GERENTE_UNIDADE,
                "unidades": ["SP-01"],
            },
        ]

        for data in usuarios_data:
            # Criar ou obter usuário
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "is_staff": data["is_staff"],
                    "is_superuser": data["is_superuser"],
                },
            )

            # Definir senha (apenas se for novo usuário ou sempre resetar)
            if created:
                user.set_password(data["password"])
                user.save()

            # Adicionar ao grupo
            grupo = grupos[data["grupo"]]
            user.groups.add(grupo)

            # Criar ou atualizar profile
            profile, profile_created = Profile.objects.get_or_create(
                user=user, defaults={"role": data["role"]}
            )

            # Associar unidades
            if data["unidades"]:
                unidades_list = [unidades[codigo] for codigo in data["unidades"]]
                profile.unidades.set(unidades_list)

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Usuário criado: {user.username} "
                        f'(senha: {data["password"]}) - {data["grupo"]}'
                    )
                )
            else:
                self.stdout.write(
                    f'  - Usuário já existe: {user.username} - {data["grupo"]}'
                )
