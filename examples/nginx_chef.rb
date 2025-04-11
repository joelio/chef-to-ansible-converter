# Example Chef recipe for installing and configuring Nginx

# Install nginx package
package 'nginx' do
  action :install
end

# Create document root directory
directory '/var/www/html' do
  owner 'www-data'
  group 'www-data'
  mode '0755'
  recursive true
  action :create
end

# Create nginx configuration from template
template '/etc/nginx/nginx.conf' do
  source 'nginx.conf.erb'
  variables(
    server_name: node['nginx']['server_name'],
    port: node['nginx']['port'],
    document_root: '/var/www/html'
  )
  notifies :reload, 'service[nginx]'
end

# Create default site configuration
template '/etc/nginx/sites-available/default' do
  source 'default-site.erb'
  variables(
    server_name: node['nginx']['server_name'],
    document_root: '/var/www/html'
  )
  notifies :reload, 'service[nginx]'
end

# Enable default site
link '/etc/nginx/sites-enabled/default' do
  to '/etc/nginx/sites-available/default'
  notifies :reload, 'service[nginx]'
end

# Start and enable nginx service
service 'nginx' do
  action [:enable, :start]
  supports status: true, restart: true, reload: true
end

# Conditional logic based on platform
if platform_family?('debian')
  # Update apt cache
  apt_update 'update' do
    action :update
  end
end
