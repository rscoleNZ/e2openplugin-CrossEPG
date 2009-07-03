from enigma import *
from Components.ServiceEventTracker import ServiceEventTracker
from crossepglib import *
from crossepg_downloader import CrossEPG_Downloader
from crossepg_converter import CrossEPG_Converter
from crossepg_loader import CrossEPG_Loader
from Screens.Screen import Screen

from time import *
class CrossEPG_Auto(Screen):
	def __init__(self):
		self.session = None
		self.timer = eTimer()
		self.timer.callback.append(self.__dailyDownload)
		self.providers = list()
		self.providers_id = list()
		self.providers_last = list()
		self.current_id = -1
		self.downloader = None
		self.converter = None
		self.loader = None
		self.auto_tune = 0
		self.auto_tune_osd = 0
		self.enabled = True
	
	def enable(self):
		self.enabled = True
		
	def disable(self):
		self.enabled = False
		
	def init(self, session):
		self.session = session
		Screen.__init__(self, session)
		config = CrossEPG_Config()
		config.load()
		providers = config.getAllProviders()
		for provider in providers:
			self.providers.append(provider)
			self.providers_id.append(config.getChannelID(provider))
			self.providers_last.append(0)
		
		self.auto_tune = config.auto_tune
		self.auto_tune_osd = config.auto_tune_osd
		db_root = config.db_root
		if not pathExists(db_root):
			if not createDir(db_root):
				db_root = "/hdd/crossepg"
				
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
		{
			iPlayableService.evEnd: self.__stopped,
			iPlayableService.evTunedIn: self.__tuned,
		})
		
		if config.auto_boot == 1:
			try:
				f = open("%s/ext.epg.dat" % (db_root), "r")
			except Exception, e:
				self.converter = CrossEPG_Converter(self.session, self.__convertOnInitEnded)
			else:
				f.seek(4);
				if f.read(13) == "ENIGMA_EPG_V7":
					self.loader = CrossEPG_Loader(self.session, self.__loaderEnded)
				else:
					self.converter = CrossEPG_Converter(self.session, self.__convertOnInitEnded)
				f.close()
		
		self.dailyStart()
		
	def dailyStart(self, hours = None, minutes = None, tomorrow = False):
		config = CrossEPG_Config()
		config.load()
		
		if not hours or not minutes:
			if not config.auto_daily:
				print "[CrossEPG_Auto] daily download disabled"
				return
			self.hours = config.auto_daily_hours
			self.minutes = config.auto_daily_minutes
		else:
			self.hours = hours
			self.minutes = minutes
		
		self.timer.stop()
		now = time()
		ttime = localtime(now)
		ltime = (ttime[0], ttime[1], ttime[2], self.hours, self.minutes, 0, ttime[6], ttime[7], ttime[8])
		stime = mktime(ltime)
		if tomorrow:
			stime += 60*60*24
		if stime < now + 2:
			stime += 60*60*24
		
		delta = int(stime - now);
		if delta <= 0:
			delta = 1
			
		print "[CrossEPG_Auto] enabled timer in %d minutes" % (delta / 60)
		self.timer.start(1000*delta, 1)
		
	def dailyStop(self):
		print "[CrossEPG_Auto] daily download disabled"
		self.timer.stop()
		
	def stop(self):
		if self.downloader:
			self.current_id = -1
			self.downloader.quit()
			self.downloader = None
		if self.converter:
			self.converter.quit()
			self.converter = None
		if self.loader:
			self.loader.quit()
			self.loader = None
		
	def __dailyDownload(self):
		print "[CrossEPG_Auto] daily action! starting downloader"
		if self.enabled:
			self.stop()
			self.session.open(CrossEPG_Downloader, self.__dailyDownloadEnded)
			self.enabled = False
			self.dailyStart(self.hours, self.minutes, True)
		else:
			print "[CrossEPG_Auto] another download is in progress... skipped"
		
	def __dailyDownloadEnded(self, session, ret):
		if ret:
			self.session.open(CrossEPG_Converter, self.__dailyConvertEnded)
		else:
			self.enabled = True
	
	def __dailyConvertEnded(self, session, ret):
		if ret:
			self.session.open(CrossEPG_Loader, self.__dailyLoaderEnded)
		else:
			self.enabled = True
		
	def __dailyLoaderEnded(self, session, ret):
		self.enabled = True
		
	def __downloadEnded(self, session, ret):
		self.downloader = None
		if ret and self.current_id > -1:
			print "[CrossEPG_Auto] download ok! ignore others download on this provider for 60 minutes"
			self.providers_last[self.current_id] = time() + 3600
			if self.auto_tune_osd == 1:
				self.session.open(CrossEPG_Converter, self.__convertEnded)
			else:
				self.converter = CrossEPG_Converter(self.session, self.__convertEnded)
		self.current_id = -1

	def __convertOnInitEnded(self, session, ret):
		self.converter = None
		if ret:
			self.loader = CrossEPG_Loader(self.session, self.__loaderEnded)

	def __convertEnded(self, session, ret):
		self.converter = None
		if ret:
			if self.auto_tune_osd == 1:
				self.session.open(CrossEPG_Loader, self.__loaderEnded)
			else:
				self.loader = CrossEPG_Loader(self.session, self.__loaderEnded)
	
	def __loaderEnded(self, session, ret):
		self.loader = None
		
	def __stopped(self):
		if self.downloader:
			self.current_id = -1
			self.downloader.quit()
			self.downloader = None
			
	def __tuned(self):
		if self.auto_tune == 1 and self.enabled:
			sservice = self.session.nav.getCurrentlyPlayingServiceReference()
			if sservice:
				service = sservice.toString()
				count = 0
				for provider in self.providers:
					if self.providers_id[count] == service:
						print "[CrossEPG_Auto] match with provider %s" % (provider)
						if self.providers_last[count] > time():
							print "[CrossEPG_Auto] epg already downloaded... download ignored"
						else:
							self.stop()
							self.current_id = count
							if self.auto_tune_osd == 1:
								self.session.open(CrossEPG_Downloader, self.__downloadEnded, provider)
							else:
								self.downloader = CrossEPG_Downloader(self.session, self.__downloadEnded, provider)
					count += 1
		
crossepg_auto = CrossEPG_Auto()