#!/bin/sh

mydir=$(readlink -f $0)
mydir=$(dirname "$mydir")

if [ ! -r "${mydir}/bot.cfg" ]; then
	echo "'bot.cfg' is missing. Have you copied 'bot.cfg.example'?"
	exit 2
fi

case $1 in
	start)
		[ ! -d "${mydir}/logs" ] && mkdir "${mydir}/logs"

		"${mydir}/willie/willie.py" -c "${mydir}/bot.cfg" --fork
		;;
	stop)
		"${mydir}/willie/willie.py" -c "${mydir}/bot.cfg" --quit
		;;

	restart)
		"$0" stop
		sleep 2
		"$0" start
		;;

	reload)
		echo "Not supported by script."
		exit 2
		;;

	*)
		echo "Unknown command. Please give 'start', 'stop' or 'restart'."
		exit 1
		;;
esac
