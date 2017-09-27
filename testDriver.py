# py -m pip install -U __
# pylint: disable=C
import discord
import os
from discord.ext import commands
import configparser
import getpass
import psycopg2
import urllib.parse
import random
import asyncio
import codecs as codex
import math
import time
import subprocess
import sys
from io import StringIO
import logging

configFile = "botMain.settings"

#check if config file exists, if not, input manually
if not os.path.isfile(configFile):
  DISCORD_API_ID = getpass.getpass('Discord API: ')
  token = getpass.getpass('Token: ')
  wolframid = getpass.getpass('Wolframalpha: ')
  ip = "172.93.48.238:25565"
  description = "Bot of the CSSS"
  postgrespass = getpass.getpass('Database Password: ')
  mashape_key = getpass.getpass('Mashape Key: ')
  local_postgres_pw = getpass.getpass('Database Password: ')
  imgur_id = getpass.getpass('Imgur client id: ')
else:
  #Load the config file
  config = configparser.ConfigParser()
  config.read(configFile)
  description = config.get("Discord", "Description")
  wolframid = config.get("Wolfram", "TokenId")
  DISCORD_API_ID = config.get("Discord", "API_ID")
  token = config.get("Discord", "Token")
  ip = "172.93.48.238:25565"
  postgrespass = config.get("Postgres", "Password")
  mashape_key = config.get("Mashape", "Token")
  local_postgres_pw = config.get("LocalPG", 'Password')
  imgur_id = config.get("Imgur", "client_id")

# SQL SETUP------------------------------------------------------------------------------
urllib.parse.uses_netloc.append("postgres")
conn = psycopg2.connect("port='5432' user='zocnciwk' host='tantor.db.elephantsql.com' password='"+postgrespass+"'")
cur = conn.cursor()
# SQL SETUP------------------------------------------------------------------------------

bot = commands.Bot(command_prefix='.', description=description)
bot.wolframid = wolframid
bot.mcip = ip
bot.remove_command("help")
bot.mashape_key = mashape_key
bot.imgur_id = imgur_id
bot.lang_url = config.get("Translate","url")
EXP_COOLDOWN_TIMER = 3 #seconds

# creating a 2D empty array for exp queues
expQueue = []

@bot.event
async def on_ready():
  print('Logged in as')
  print(bot.user.name)
  print('------')
  await bot.change_presence(game=discord.Game(name='Yes my master'))

@bot.event
async def on_message(message):
  # DATABASE OPERATIONS. DISABLE UNLESS ACTUALLY RUNNING AS SERVICE
  # print(message.author.name+"#"+message.author.discriminator)
  if validate(message):
    await add(message)
  await bot.process_commands(message)

@bot.command()
async def test():
  await bot.say('testing')

# used to update the queue
async def update():
  await bot.wait_until_ready()
  print("ready")
  while not bot.is_closed:
      for i, item in enumerate(expQueue):
          if time.time() - item[1] >= EXP_COOLDOWN_TIMER:
              print("entry expired")
              del expQueue[i]
      await asyncio.sleep(1)

# Check if author is currently on cooldown
def validate(message):
  for item in expQueue:
    if message.author.id == item[0]:
      # author on cooldown
      return False
  # author not on cooldown, add author id and current time to queue
  print("entry added to queue")
  expQueue.append([message.author.id, time.time()])
  return True

# handles adding new users and updating existing user exp to database
async def add(message):
  database = 'experience'
  entry = db_select(database, message.author.id)
  if entry == None:
    # user not in database
    exp_amount = random.randint(15, 25)
    print("entry added to db")
    db_insert(database, ['name', 'user_id', 'exp', 'level', 'true_experience'], [message.author.name, message.author.id, exp_amount, currentLevel(exp_amount), exp_amount])
  else:
    list(entry)
    changeInExp = random.randint(15, 25)
    if changeInLevel(changeInExp, entry[3], entry[4]) == 'levelup':
      # user's levelled up
      db_update(database, 'level', currentLevel(entry[3]), 'user_id', message.author.id)
      await bot.send_message(message.channel, "{} has leveled up to {}".format(message.author.name, currentLevel(entry[3])))

    # if changeInLevel(changeInExp, entry[3], entry[4]) == 'leveldown':
    #   # user's levelled down
      # db_update(database, 'level', currentLevel(entry[3]), 'user_id', message.author.id)
    # update user new experience
    print("entry update exp")

    db_update(database, 'exp', entry[3]+changeInExp, 'user_id', message.author.id)
    db_update(database, 'true_experience', entry[3]+changeInExp, 'user_id', message.author.id)


def changeInLevel(change, experience, currLevel):
  curr_experience = experience + change
  new_level = currentLevel(experience)
  if new_level > currLevel:
    # user has leveled up
    return 'levelup'


# outputs closest level based on total experience
def currentLevel(experience):
  if experience is 0:
    return 0
  # grab the template experience list from database
  cur.execute("SELECT level, total_experience FROM template ORDER BY level")
  templateList = cur.fetchall()
  for level in templateList:
    if experience <= level[1]:
      return level[0]-1
  # should never reach here, error out with -1
  bot.say("Something went wrong.")
  return -1

# outputs current exp for level (not total exp)
def currentExp(level, experience):
  cur.execute("SELECT total_experience FROM template WHERE level = {}".format(level))
  return experience - cur.fetchone()[0]

# formula used to calculate exact experience needed for next level
# x = level
def calcLevel(x):
  return 5*math.pow(x, 2) + 50*x + 100

@bot.command(pass_context = True)
async def rank(ctx):
  cur.execute('SELECT * FROM (SELECT *, row_number() OVER(ORDER BY exp DESC) FROM experience) AS filter WHERE filter.user_id={}'.format(ctx.message.author.id))
  res = list(cur.fetchone())
  cur.execute('SELECT count(*) from experience')
  totalUsers = cur.fetchone()[0]
  level = res[4]
  totalExperience = res[3]
  currentExperience = currentExp(level, totalExperience)
  rank = res[6]
  nextLevel = calcLevel(int(level)+1)

  embed = discord.Embed(colour=discord.Colour(0x1d86c9))
  embed.set_author(name=ctx.message.author.nick, icon_url=ctx.message.author.avatar_url)
  embed.set_footer(text="CSSS-Minion")
  embed.add_field(name="Rank", value="{}/{}".format(rank, totalUsers), inline=True)
  embed.add_field(name="Level", value=level, inline=True)
  embed.add_field(name="Experience", value="{} / {} XP [{} total]".format(currentExperience, nextLevel, totalExperience), inline=True)

  await bot.say(embed=embed)

@bot.command(pass_context = True)
async def levels(ctx):
  await bot.say("Henry hasn't gotten around to making this yet :(")


# database accessors ----------------------------------------------------------------------------
def db_update(database, column, value, where, query):
  cur.execute("UPDATE {} SET {} = {} WHERE {} = {}".format(database, column, value, where, query))
  conn.commit()

def db_insert(database, name, value):
  cur.execute("INSERT INTO {} ({}) VALUES ({})".format(database, ', '.join(str(n) for n in name), "'{0}'".format("','".join( str(v) for v in value))))
  conn.commit()

def db_select(database, query, item = '*'):
  cur.execute("SELECT {} FROM {} WHERE user_id = ({})".format(', '.join(str(n) for n in item), database, query))
  return cur.fetchone()

bot.loop.create_task(update())
bot.run(token)