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

alias log='tail -f /var/log/httpd/* /var/log/cfn-* /var/log/eb-*'
alias logs='tail -f /var/log/httpd/* /var/log/cfn-* /var/log/eb-*'
alias logeb="/var/log/cfn-* /var/log/eb-*"
alias logc="/var/log/cfn-* /var/log/eb-*"
alias loghtpd='tail -f /var/log/httpd/*'

alias sudo="sudo "
alias n="nano "
alias sn="sudo nano "

alias pyc='find . -type f -name "*.pyc" -delete -print'
alias htop="htop -d 5"

alias u="cd .."
alias uu="cd ../.."
alias uuu="cd ../../.."

alias ls='ls --color=auto'
alias la='ls -A'
alias ll='ls -Alh'
alias lh='ls -lhX --color=auto'

alias py="python"
alias ipy="ipython"

alias ls='ls --color=auto -h'
