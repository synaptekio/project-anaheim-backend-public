# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

# User specific aliases and functions

# enable the python venv, load the current environment variables for the ssh session.
source /var/app/venv/*/bin/activate 

`/opt/elasticbeanstalk/bin/get-config optionsettings | jq '."aws:elasticbeanstalk:application:environment"' | jq -r 'to_entries | .[] | "export \(.key)=\(.value)"'`

cd /var/app
cd /var/app/current

alias db='cd /var/app/current; python /var/app/current/manage.py shell_plus'
alias restart='sudo killall -s 1 supervisord; htop -u apache'

alias log='sudo tail -f /var/log/httpd/access_log /var/log/httpd/error_log /var/log/cfn-* /var/log/eb-* /var/log/messages'
alias logs='log'
alias logeb="/var/log/cfn-* /var/log/eb-*"
alias loghttpd='tail -f /var/log/httpd/*'
alias logdjango='sudo tail -f  /var/log/web.stdout.log'
alias logd='logdjango'
alias loggunicorn='sudo tail -f /var/log/messages'
alias logg='loggunicorn'

alias sudo="sudo "
alias n="nano "
alias no="nano -Iwn "
alias sn="sudo nano "
alias sno="sudo nano -Iwn "

alias pyc='find . -type f -name "*.pyc" -delete -print'
alias htop="htop -d 5"

alias u="cd .."
alias uu="cd ../.."
alias uuu="cd ../../.."

alias ls='ls --color=auto'
alias l='ls'
alias la='ls -A'
alias ll='ls -Alh'
alias lh='ls -lhX --color=auto'

alias py="python"
alias ipy="ipython"

alias ls='ls --color=auto -h'
