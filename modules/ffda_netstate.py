# -*- coding: utf-8 -*-
from __future__ import print_function

import willie

import requests
import json
import shelve
import time
import traceback

from ffda_lib import pretty_date, day_changed


def setup(bot):
    hs = shelve.open("ffda-highscore.shelve", writeback=True)

    # total highscore
    if 'nodes' not in hs:
        hs['nodes'] = 0
        hs['nodes_dt'] = time.time()
    if 'clients' not in hs:
        hs['clients'] = 0
        hs['clients_dt'] = time.time()

    # end of day highscore, also clean up if we load a daychange from file
    try:
        if day_changed(hs['daily_dt']):
            reset_highscore(hs)
    except KeyError:
        reset_highscore(hs)

    bot.memory['ffda'] = {'highscore': hs}


def reset_highscore(highscore):
    highscore['daily_nodes'] = 0
    highscore['daily_nodes_dt'] = time.time()
    highscore['daily_clients'] = 0
    highscore['daily_clients_dt'] = time.time()
    highscore['daily_dt'] = time.time()


def shutdown(bot):
    try:
        hs = bot.memory['ffda']['highscore']
        hs.close()
    except KeyError:
        pass


@willie.module.interval(15)
def update(bot):
    result = requests.get(bot.config.freifunk.ffmap_nodes_uri)
    try:
        mapdata = json.loads(result.text)
    except ValueError:
        print(traceback.format_exc())
        return

    gateways = 0
    nodes = 0
    clients = 0
    for node in mapdata['nodes']:
        try:
            if not node['flags']['online']:
                continue
            if node['flags']['gateway']:
                gateways += 1
                continue
        except KeyError:
            continue

        nodes += 1
        clients += node.get('clientcount', 0)

    bot.memory['ffda']['status'] = (nodes, gateways, clients)
    update_highscore(bot, nodes, gateways, clients)


def update_highscore(bot, nodes, gateways, clients):
    hs = bot.memory['ffda']['highscore']

    # total highscore
    new_highscore = False
    if nodes > hs['nodes']:
        hs['nodes'] = nodes
        hs['nodes_dt'] = time.time()
        new_highscore = True
    if nodes > hs['daily_nodes']:
        hs['daily_nodes'] = nodes
        hs['daily_nodes_dt'] = time.time()

    if clients > hs['clients']:
        hs['clients'] = clients
        hs['clients_dt'] = time.time()
        new_highscore = True
    if clients > hs['daily_clients']:
        hs['daily_clients'] = clients
        hs['daily_clients_dt'] = time.time()

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
    hs = bot.memory['ffda']['highscore']
    nodes, gateways, clients = bot.memory['ffda']['status']

    tpl = "Derzeit sind {} Gateways, {} Nodes (^{}) und {} Clients (^{}) online."
    msg = tpl.format(gateways, nodes, hs['daily_nodes'], clients, hs['daily_clients'])
    bot.say(msg)
    print(msg)


@willie.module.commands('highscore')
def highscore(bot, trigger):
    hs = bot.memory['ffda']['highscore']

    tpl = "Der Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
    msg = tpl.format(hs['nodes'], pretty_date(hs['nodes_dt']),
                     hs['clients'], pretty_date(hs['clients_dt']))
    bot.say(msg)
    print(msg)
