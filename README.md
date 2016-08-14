This is a basic slackbot that can run markets and allow people to trade via slack.


```
install python 3, set up a virtualenv
pip install slackclient
python marketslackbot.py
```

This bot only responds to messages in a channel, so make sure you invite marketbot to a channel first!  See below to read the commands and helpstring.

```
@marketbot help
@marketbot details
bid <price:float>
bid <price:float> for <qty:int>
ask <price:float>
ask <price:float> for <qty:int>
hit <qty:int>
lift <qty:int>

marketstart <asset:string#no_spaces>   // launch a new market in <asset>
marketsettle <price:float>  // settle current market at <price> and close the market
pos    // view entire market's positions
mypos  // view your current positions
book   // view entire market book and description
mybook // view your current orders
stat   // view the description, bid-ask spread, and last trade price of the market
clear  // removes all of your orders

A quick run through on some of the finer points of working with marketbot:

Marketbot allows one market at a time per channel. (Sorry, I know derivatives and arbitrage would be fun)
A market is in some asset which *you* will manually settle at a final price (For example, you could trade on the probability of an event, and you would settle at 1 if it happened, 0 if it didn't).
You can short arbitrarily with no costs - all assets are synthetics that will settle to cash at the <price> set by the marketsettle command.  That will then be added (or subtracted if you're short) to your final cash position.
Bids and Asks should be treated as standing limit orders with no Fill or Kill provision (partial orders will happen).  A bid will fill any standing offers at the asking price if it's less than the bid (vice versa applies).
Because I'm lazy, if you hit or lift yourself, you'll trade with yourself - this has no net effect on your positions as they will net to 0, but will eliminate your standing trades and also decrease the quantity that you end up hitting/lifting by.
Trades resolve by best price, and then FIFO in event of ties.
```