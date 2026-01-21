# Render Deployment Guide for DopeEvents

## Prerequisites
1. Render account
2. Git repository set up
3. Render CLI installed (optional)

## Deployment Steps

### 1. Sign up for Render
- Go to https://render.com
- Sign up with GitHub, GitLab, or email
- Verify your email

### 2. Connect Your Repository
1. Click "New +" button
2. Select "Web Service"
3. Connect your GitHub repository: `Siblore/vibeninjas`
4. Select the `DopeEvents` repository
5. Choose branch: `master`

### 3. Configure Web Service

#### Basic Settings:
- **Name**: dopeevents-web
- **Environment**: Python 3
- **Region**: Choose nearest to your users
- **Branch**: master

#### Build Settings:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn DopeEvents.wsgi:application --bind 0.0.0.0:$PORT`

#### Environment Variables:
```
DJANGO_SETTINGS_MODULE=DopeEvents.settings
SECRET_KEY=your-very-secret-key-here
DEBUG=False
ALLOWED_HOSTS=*
```

### 4. Set Up Database

#### Create PostgreSQL Database:
1. In Render dashboard, click "New +"
2. Select "PostgreSQL"
3. **Name**: dopeevents-db
4. **Database Name**: dopeevents
5. **User**: dopeevents
6. **Plan**: Free (to start)
7. Click "Create Database"

#### Connect Database to App:
1. Go to your web service settings
2. Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Copy from database dashboard (Connection String)
3. Restart your service

### 5. Deploy

#### Automatic Deployment:
- Render will automatically deploy when you push to master branch
- Manual deployment: Click "Manual Deploy" in dashboard

#### First Deployment:
1. Commit and push your changes:
   ```bash
   git add .
   git commit -m "Configure for Render deployment"
   git push origin master
   ```
2. Monitor deployment in Render dashboard
3. Wait for deployment to complete

## Environment Variables Configuration

### Required Variables:
```bash
# Django Core
DJANGO_SETTINGS_MODULE=DopeEvents.settings
SECRET_KEY=your-very-secret-key-here
DEBUG=False
ALLOWED_HOSTS=*

# Database
DATABASE_URL=postgresql://username:password@host:port/database

# Optional Services
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Payment Integrations
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
```

## Post-Deployment Setup

### 1. Run Database Migrations
```bash
# Connect to service shell (Render dashboard → Service → Shell)
python manage.py migrate
```

### 2. Create Superuser
```bash
python manage.py createsuperuser
```

### 3. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 4. Verify Deployment
- Check your service URL: `https://dopeevents-web.onrender.com`
- Test admin panel: `https://dopeevents-web.onrender.com/admin`
- Check logs in Render dashboard

## render.yaml Configuration

Your project includes a `render.yaml` file for infrastructure-as-code deployment:

```yaml
services:
  - type: web
    name: dopeevents-web
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn DopeEvents.wsgi:application --bind 0.0.0.0:$PORT
    healthCheckPath: /
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: DopeEvents.settings
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: false
      - key: DATABASE_URL
        fromDatabase:
          name: dopeevents-db
          property: connectionString
      - key: ALLOWED_HOSTS
        value: "*"
    autoDeploy: true

  - type: pserv
    name: dopeevents-db
    plan: free
    databaseName: dopeevents
    user: dopeevents
```

## Using render.yaml

### Option 1: Render Dashboard
1. Go to Render dashboard
2. Click "New +"
3. Select "Blueprint"
4. Upload your `render.yaml` file
5. Click "Apply"

### Option 2: Render CLI
```bash
# Install Render CLI
npm install -g @render/cli

# Login
render login

# Deploy from yaml
render blueprint
```

## Cost and Plans

### Free Tier (Great for Development):
- **Web Service**: 750 hours/month
- **Database**: 256MB RAM, 1 connection
- **Bandwidth**: 100GB/month
- **Custom Domain**: Not included

### Starter Plan ($7/month):
- **Web Service**: More resources
- **Database**: 1GB RAM, 10 connections
- **Bandwidth**: 500GB/month
- **Custom Domain**: Included

## Troubleshooting

### Common Issues:

#### 1. Database Connection Error
- Check DATABASE_URL environment variable
- Verify database is running
- Check database credentials

#### 2. Static Files Not Loading
- Run `python manage.py collectstatic --noinput`
- Check WHITENOISE settings
- Verify static files configuration

#### 3. Application Error
- Check Render logs: Dashboard → Service → Logs
- Verify environment variables
- Check build process

#### 4. Migration Issues
- Connect to service shell
- Run migrations manually
- Check database connection

### Getting Help:
- **Render Docs**: https://render.com/docs
- **Community**: https://community.render.com
- **Support**: support@render.com

## Security Best Practices

1. **Use HTTPS**: Render provides automatic SSL
2. **Environment Variables**: Store secrets in Render dashboard
3. **Database Security**: Use strong passwords
4. **Regular Updates**: Keep dependencies updated
5. **Monitor Logs**: Check for security issues

## Monitoring and Maintenance

### Health Checks:
- Render automatically checks `/` endpoint
- Configure custom health check in render.yaml
- Monitor service status in dashboard

### Backups:
- **Database**: Automatic daily backups (paid plans)
- **Manual Backup**: Export data regularly
- **Code**: Version control with Git

### Performance Monitoring:
- **Metrics**: Available in dashboard
- **Response Times**: Monitor user experience
- **Error Tracking**: Check logs regularly

## Alternative Deployment Options

### 1. Manual Setup (Web Dashboard)
- Use Render web interface
- Step-by-step configuration
- Good for beginners

### 2. Infrastructure as Code (render.yaml)
- Version-controlled configuration
- Reproducible deployments
- Better for teams

### 3. Render CLI
- Command-line deployment
- Automation friendly
- CI/CD integration

## Migration from Other Platforms

### From Heroku:
1. Export database: `heroku pg:backups:download`
2. Import to Render database
3. Update environment variables
4. Deploy code

### From Google Cloud:
1. Export Cloud SQL data
2. Import to Render PostgreSQL
3. Update configuration
4. Deploy with render.yaml

## Production Checklist

Before going live:

- [ ] All environment variables set
- [ ] Database migrations applied
- [ ] Superuser created
- [ ] Static files collected
- [ ] Custom domain configured (if needed)
- [ ] SSL certificate verified
- [ ] Payment integrations tested
- [ ] Email functionality tested
- [ ] Performance optimized
- [ ] Monitoring set up
- [ ] Backup strategy in place
