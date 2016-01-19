This is a basic slackbot that can run markets and allow people to trade via slack.


```
mkdir ~/tmpsrc
cd ~/tmpsrc
wget http://www.python.org/ftp/python/2.7.6/Python-2.7.6.tgz
cd Python-2.7.6/
mkdir ~/.localpython276
./configure --prefix=/home/justin/.localpython276
make
make install
rm -rf ~/tmpsrc
```



```
pip install slackclient
```

want the bot to react to @mentions and IMs.  Will need to maintain an IM channel ID cache so that I don't have to make API requests for every single message to verify that it is an IM.  Other than that, I can just look for @mentions.

Or, it could run markets *only* in its channels, in which case it would only react to @mentions, which would definitely be a heck of a lot easier.



api calls look like this:

```
clist = json.loads(sc.api_call("channels.list", exclude_archived=1).decode("utf-8"))
```