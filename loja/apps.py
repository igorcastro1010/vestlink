from django.apps import AppConfig


class LojaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "loja"

    def ready(self):
        # Apply the reverse monkeypatch to make existing templates and code
        # automatically adapt to subdomain/custom domain urls
        import django.urls
        from loja.middleware import get_current_tenant

        original_reverse = django.urls.reverse

        def tenant_aware_reverse(viewname, urlconf=None, args=None, kwargs=None, current_app=None):
            loja = get_current_tenant()
            if loja:
                # If a tenant is active on the request, rewrite the reversed URL
                # to the simplified URLs without the slug parameter.
                if viewname in (
                    "catalogo",
                    "catalogo_curto",
                    "produto_detalhe",
                    "produto_detalhe_curto",
                    "whatsapp_produto",
                    "whatsapp_carrinho",
                ):
                    new_args = list(args) if args else []
                    new_kwargs = kwargs.copy() if kwargs else {}

                    # Strip slug from kwargs
                    new_kwargs.pop("slug", None)

                    # Strip slug from args (always the first parameter if present)
                    if new_args and new_args[0] == loja.slug:
                        new_args.pop(0)

                    return original_reverse(viewname, urlconf=urlconf, args=new_args, kwargs=new_kwargs, current_app=current_app)
            
            return original_reverse(viewname, urlconf=urlconf, args=args, kwargs=kwargs, current_app=current_app)

        django.urls.reverse = tenant_aware_reverse
