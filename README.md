# VestLink

SaaS em Django para lojas de roupas criarem um catalogo digital profissional, com link proprio, painel do lojista, produtos, fotos, tamanhos, cores, leads, checkout Premium e venda pelo WhatsApp.

## Rodar localmente

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Abra:

- Site principal: http://127.0.0.1:8000/
- Painel: http://127.0.0.1:8000/painel/
- Catalogo demo: http://127.0.0.1:8000/c/bela-meunier/

## Deploy na Vercel

A Vercel publica este projeto usando `api/index.py`, que expõe a variavel WSGI `app` para o runtime Python serverless.

### 1. Criar banco de dados no Supabase

Para producao, use o Postgres do Supabase. No painel do Supabase:

1. Crie um projeto.
2. Va em **Project Settings > Database > Connection string**.
3. Copie a URL em **Transaction pooler > URI**.
4. Troque `[YOUR-PASSWORD]` pela senha do banco.

O formato fica assim:

```bash
postgresql://postgres.[project-ref]:senha@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

SQLite nao deve ser usado na Vercel para producao, porque o ambiente serverless nao e feito para gravar banco local de forma persistente.

### 2. Configurar variaveis de ambiente na Vercel

No painel do projeto na Vercel, adicione:

```bash
DJANGO_SECRET_KEY=sua-chave-secreta-forte
DJANGO_DEBUG=0
SUPABASE_DATABASE_URL=postgresql://postgres.[project-ref]:senha@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
DATABASE_CONN_MAX_AGE=0
DATABASE_DISABLE_SERVER_SIDE_CURSORS=1
VESTLINK_BASE_URL=https://seu-projeto.vercel.app
```

Se voce conectar pelo Marketplace da Vercel com prefixo `SUPABASE_`, a variavel criada sera `SUPABASE_POSTGRES_URL` e o Django tambem usa ela automaticamente. `SUPABASE_DATABASE_URL` tem prioridade sobre `SUPABASE_POSTGRES_URL`.

Para usar o Supabase Auth na confirmacao de e-mail do cadastro, mantenha tambem:

```bash
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=sua-chave-anon-ou-publishable
SUPABASE_AUTH_EMAIL_CONFIRMATION=1
SUPABASE_EMAIL_REDIRECT_URL=https://vestlink.vercel.app/cadastro/supabase-confirmar/
```

No painel do Supabase, va em **Authentication > URL Configuration**:

- **Site URL**: `https://vestlink.vercel.app`
- **Redirect URLs**: adicione `https://vestlink.vercel.app/cadastro/supabase-confirmar/`

Em **Authentication > Providers > Email**, deixe **Confirm email** ativado. O Supabase tem envio padrao para testes, mas possui limite baixo; para producao, configure SMTP no proprio Supabase Auth.

Se usar dominio proprio:

```bash
DJANGO_ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br
VESTLINK_BASE_URL=https://seudominio.com.br
```

Se for ativar e-mail de confirmacao de conta com Resend:

```bash
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxx
RESEND_FROM_EMAIL=VestLink <noreply@seudominio.com.br>
DEFAULT_FROM_EMAIL=VestLink <noreply@seudominio.com.br>
```

Para enviar para clientes reais, o dominio do `RESEND_FROM_EMAIL` precisa estar verificado no Resend. Sem `RESEND_API_KEY` ou SMTP configurado, o Django usa o backend de console e o e-mail aparece apenas nos logs.

Se preferir SMTP tradicional:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seuprovedor.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=usuario
EMAIL_HOST_PASSWORD=senha
DEFAULT_FROM_EMAIL=VestLink <contato@seudominio.com.br>
```

Se for ativar Mercado Pago:

```bash
MERCADO_PAGO_ACCESS_TOKEN=seu-token
MERCADO_PAGO_USE_SANDBOX=0
```

### 3. Subir pela CLI da Vercel

```bash
npm i -g vercel
vercel login
vercel
vercel --prod
```

### 4. Rodar migracoes no banco de producao

Depois de criar o banco e configurar a URL do Supabase, rode as migracoes apontando para o banco de producao:

```bash
set SUPABASE_DATABASE_URL=postgresql://postgres.[project-ref]:senha@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
python manage.py migrate
```

No PowerShell:

```powershell
$env:SUPABASE_DATABASE_URL="postgresql://postgres.[project-ref]:senha@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
python manage.py migrate
```

### 5. Criar usuario administrador

```bash
set SUPABASE_DATABASE_URL=postgresql://postgres.[project-ref]:senha@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
python manage.py createsuperuser
```

No PowerShell:

```powershell
$env:SUPABASE_DATABASE_URL="postgresql://postgres.[project-ref]:senha@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
python manage.py createsuperuser
```

## Observacoes importantes

- O arquivo `db.sqlite3` nao e enviado para a Vercel.
- A pasta `media/` tambem nao e enviada, porque uploads locais nao persistem bem na Vercel.
- Para lancar de verdade com fotos de produtos, o proximo passo e ligar uploads em um storage externo, como Cloudinary, S3, Supabase Storage ou Vercel Blob.
- O cupom atual de lancamento e `VESTLINK10`.
