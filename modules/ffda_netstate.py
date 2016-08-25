# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shelve
import traceback
import pendulum

import requests
from requests.compat import urljoin

import willie


def setup(bot):
    hs = shelve.open("ffda-highscore", writeback=True)

    # total highscore
    if 'nodes' not in hs:
        hs['nodes'] = 0
        hs['nodes_dt'] = pendulum.now()
    if 'clients' not in hs:
        hs['clients'] = 0
        hs['clients_dt'] = pendulum.now()

    # end of day highscore, also clean up if we load a daychange from file
    try:
        if day_changed(hs['daily_dt']):
            reset_highscore(hs)
    except KeyError:
        reset_highscore(hs)

    bot.memory['ffda'] = {'highscore': hs}


def reset_highscore(highscore):
    highscore['daily_nodes'] = 0
    highscore['daily_nodes_dt'] = pendulum.now()
    highscore['daily_clients'] = 0
    highscore['daily_clients_dt'] = pendulum.now()
    highscore['daily_dt'] = pendulum.now()


def shutdown(bot):
    try:
        hs = bot.memory['ffda']['highscore']
        hs.close()
    except KeyError:
        pass


@willie.module.interval(15)
def update(bot):
    result = requests.get(bot.config.freifunk.ffmap_nodes_uri)
    result.encoding = "UTF-8"
    try:
        mapdata = json.loads(result.text)
    except ValueError:
        print(traceback.format_exc())
        return

    gateway_set = set()
    nodes = 0
    clients = 0
    for node in mapdata['nodes']:
        try:
            if not node['flags']['online']:
                continue
            if 'gateway' in node['statistics']:
                gateway_set.add(node['statistics']['gateway'])
        except KeyError:
            continue

        nodes += 1
        try:
            clients += node['statistics'].get('clients', 0)
        except KeyError:
            pass

    bot.memory['ffda']['status'] = (nodes, len(gateway_set), clients)
    try:
        update_highscore(bot, nodes, len(gateway_set), clients)
    except ValueError:
        print('Warning: Unable to update highscore on closed shelve.')
        print(traceback.format_exc())


def update_highscore(bot, nodes, gateways, clients):
    hs = bot.memory['ffda']['highscore']

    # total highscore
    new_highscore = False
    if nodes > hs['nodes']:
        hs['nodes'] = nodes
        hs['nodes_dt'] = pendulum.now()
        new_highscore = True
    if nodes > hs['daily_nodes']:
        hs['daily_nodes'] = nodes
        hs['daily_nodes_dt'] = pendulum.now()

    if clients > hs['clients']:
        hs['clients'] = clients
        hs['clients_dt'] = pendulum.now()
        new_highscore = True
    if clients > hs['daily_clients']:
        hs['daily_clients'] = clients
        hs['daily_clients_dt'] = pendulum.now()

    if new_highscore:
        msg = "Neuer Highscore von {} Nodes ({}) und {} Clients ({}).".format(
                  hs['nodes'], pretty_date(hs['nodes_dt']),
                  hs['clients'], pretty_date(hs['clients_dt']))
        print(msg)
        bot.msg(bot.config.freifunk.announce_target, msg)

    # detect daychange
    if day_changed(hs['daily_dt']):
        tpl = "Der gestrige Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
        msg = tpl.format(hs['daily_nodes'], pretty_date(hs['daily_nodes_dt']),
                         hs['daily_clients'], pretty_date(hs['daily_clients_dt']))
        print(msg)
        bot.msg(bot.config.freifunk.announce_target, msg)

        reset_highscore(hs)

    bot.memory['ffda']['highscore'] = hs


@willie.module.commands('status')
def status(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    hs = bot.memory['ffda']['highscore']
    status = bot.memory['ffda'].get('status', None)

    if status is None:
        bot.say('Noch keine Daten.')
        return

    nodes, gateways, clients = status

    tpl = "Derzeit sind {} Gateways, {} Nodes (^{}) und {} Clients (^{}) online."
    msg = tpl.format(gateways, nodes, hs['daily_nodes'], clients, hs['daily_clients'])
    bot.say(msg)
    print(msg)


@willie.module.commands('highscore')
def highscore(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    hs = bot.memory['ffda']['highscore']

    tpl = "Der Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
    msg = tpl.format(hs['nodes'], pretty_date(hs['nodes_dt']),
                     hs['clients'], pretty_date(hs['clients_dt']))
    bot.say(msg)
    print(msg)


@willie.module.commands('agenda')
def agenda(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    monday = get_next_plenum()

    url = urljoin(bot.config.freifunk.padserver, 'ffda-{year}{month}{day}'.format(
        year=monday.year, month=str(monday.month).zfill(2), day=str(monday.day).zfill(2)))

    bot.say(url)


@willie.module.commands('commands')
@willie.module.commands('help')
@willie.module.commands('rtfm')
@willie.module.commands('man')
def ffda_help(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    prefix = bot.config.core.prefix
    commands = ( '{prefix}{cmd}'.format(prefix=prefix, cmd=cmd) for cmd in ('agenda', 'highscore', 'status'))

    msg = "Befehle: {cmds}".format(cmds=', '.join(commands))

    bot.say(msg)

@willie.module.require_admin
@willie.module.commands('set')
def ffda_set(bot, trigger):
    dt_format = '%Y-%m-%d %H:%M:%S'


    args = trigger.args[1].split(' ')[1:]
    mem = bot.memory['ffda']['highscore']

    key = args[0]

    value = ' '.join(args[1:])

    print(args, value)

    if key not in mem:
        bot.reply('Nope! valid keys: {}'.format(','.join(mem.keys())))
        return

    if key.endswith('_dt'):
        try:
            value = pendulum.parse(value)
        except ValueError:
            bot.reply("Invalid format, please use a format recognized by dateutil.parser for _dt's")
            return
        else:
            mem[key] = value
    else:
        try:
            value = int(value)
        except ValueError:
            bot.reply('Nope! Please supply int values.')
            return
        else:
            mem[key] = value

    bot.reply('set {} to {}'.format(key, value))

def pretty_date(dt):
    """
    Get a pendulum object and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    if dt.in_days <= 7:
        return dt.diff_for_humans()
    else:
        return dt.in_tz('Europe/Berlin').format('am %d.%m.%Y um %H:%M Uhr')

def day_changed(since):
    return since.day != pendulum.now('Europe/Berlin').day

def get_next_plenum(now=None):
    if now is None:
        now = pendulum.now('Europe/Berlin')

    next_monday = pendulum.replace(hour=19, minute=30, second=0, microsecond=0).next(pendulum.MONDAY)

    while True:
        if next_monday.week_of_month in [1,3]:
            break
        else:
            next_monday = pendulum.add(weeks=1)
    return next_monday
