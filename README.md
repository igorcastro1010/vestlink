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

### 1. Criar banco de dados

Para producao, use Postgres. Pode ser:

- Vercel Postgres/Storage
- Neon
- Supabase
- Railway Postgres

Copie a URL do banco no formato:

```bash
postgresql://usuario:senha@host:porta/banco
```

SQLite nao deve ser usado na Vercel para producao, porque o ambiente serverless nao e feito para gravar banco local de forma persistente.

### 2. Configurar variaveis de ambiente na Vercel

No painel do projeto na Vercel, adicione:

```bash
DJANGO_SECRET_KEY=sua-chave-secreta-forte
DJANGO_DEBUG=0
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
VESTLINK_BASE_URL=https://seu-projeto.vercel.app
```

Se usar dominio proprio:

```bash
DJANGO_ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br
VESTLINK_BASE_URL=https://seudominio.com.br
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

Depois de criar o banco e configurar `DATABASE_URL`, rode as migracoes apontando para o banco de producao:

```bash
set DATABASE_URL=postgresql://usuario:senha@host:porta/banco
python manage.py migrate
```

No PowerShell:

```powershell
$env:DATABASE_URL="postgresql://usuario:senha@host:porta/banco"
python manage.py migrate
```

### 5. Criar usuario administrador

```bash
set DATABASE_URL=postgresql://usuario:senha@host:porta/banco
python manage.py createsuperuser
```

No PowerShell:

```powershell
$env:DATABASE_URL="postgresql://usuario:senha@host:porta/banco"
python manage.py createsuperuser
```

## Observacoes importantes

- O arquivo `db.sqlite3` nao e enviado para a Vercel.
- A pasta `media/` tambem nao e enviada, porque uploads locais nao persistem bem na Vercel.
- Para lancar de verdade com fotos de produtos, o proximo passo e ligar uploads em um storage externo, como Cloudinary, S3, Supabase Storage ou Vercel Blob.
- O cupom atual de lancamento e `VESTLINK10`.
