for domain in \
  citytrustbanking.com \
  citytrut.com \
  citytrvst.com \
  cl0udjetairways.com \
  cloudjetarways.com \
  cloudjettairways.com \
  merdiansuites.com \
  meridainsuites.com \
  meridiansuites.co
do
  sudo ln -sfn /etc/nginx/sites-available/$domain /etc/nginx/sites-enabled/$domain
done