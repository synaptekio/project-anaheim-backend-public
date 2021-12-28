# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

# User specific aliases and functions

# load the current environment variables for the ssh session
source /var/app/current/env
cd /var/app
cd /var/app/current

alias db='cd /var/app/current; python /var/app/current/manage.py shell_plus'
alias restart='sudo killall -s 1 supervisord; htop -u apache'

alias log_commands="tail -f  /var/log/cfn-init-cmd.log"
alias logo='nano +1000000000 /var/log/httpd/error_log' #open log, go to end
alias log='tail -f /var/log/httpd/error_log' #tail follow apache log
alias logc='tail -f /var/log/httpd/*'
alias logeb='logc'

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
alias ll='ls -lh'
alias lh='ls -lhX --color=auto'

alias py="python"
alias ipy="ipython"

alias ls='ls --color=auto -h'
