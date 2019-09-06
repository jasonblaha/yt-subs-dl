import json
import os
import re
import sys
import tqdm
import webvtt
import youtube_dl

from ytchan_dl import read_urls_file, ChannelUploads

YOUTUBE_VIDEO = 'https://www.youtube.com/watch?v='

PY_FILEPATH = os.path.dirname(os.path.realpath(__file__)) 


def get_subtitle_files(subs_folder):
	subtitle_urls = []
	subtitle_filepaths = []
	for file in os.listdir(subs_folder):
		fn, ext = os.path.splitext(file)
		if not (ext == '.vtt'):
			continue
		subtitle_url = YOUTUBE_VIDEO + file[:11]
		subtitle_urls.append(subtitle_url)
		subtitle_filepath = os.path.join(subs_folder, file)
		subtitle_filepaths.append(subtitle_filepath)
	return subtitle_urls, subtitle_filepaths	


def get_to_be_handled_urls(urls, to_compare_with_urls=[]):
	to_handle_urls = []
	for url in urls:
		if url in to_compare_with_urls:
			continue
		to_handle_urls.append(url)
	return to_handle_urls #list comprehension


def DownloadSubtitles(subs_folder, urls_file, no_subs_file):
	
	#create download folder in the folder of the python file
	subs_folder = PY_FILEPATH + '/' + subs_folder
	no_subs_file = os.path.join(subs_folder, no_subs_file)

	if not os.path.isdir(subs_folder):
		os.mkdir(subs_folder)
		
	#read in file with channel uploads info
	urls, titles, pubdates, durations = read_urls_file(urls_file)
	titles_dict = dict(zip(urls,titles))
	
	#get downloaded sub titles
	sub_urls, sub_filepaths = get_subtitle_files(subs_folder)
	
	#get the urls which didn't have a subtitle
	try:
		with open(no_subs_file, 'r') as f:
			lines = f.readlines()
			no_subs_urls, no_subs_titles = zip(*[line.strip().split('\t') for line in lines])
	except FileNotFoundError:
		no_subs_urls = []
	
	completed_urls = sub_urls + list(no_subs_urls)
	
	#check which urls are to be downloaded
	to_download_urls = get_to_be_handled_urls(urls, completed_urls)
	
	if not to_download_urls:
		print('No subtitles to download!')
		return
	
	#youtube-dl options for downloading autogenerate subtitles
	ytdl_opts = {
		'quiet': True,
		'no_warnings': True,
		'skip_download': True,
		'writeautomaticsub': True,
		'subtitleslangs': ['en'],
		'outtmpl': subs_folder + '/%(id)s.%(ext)s'
	}

	#download all urls. progress bar to show progress compared to all the urls.
	with open(no_subs_file, 'a') as f, tqdm.tqdm(total=len(urls), desc='Downloading Subtitles') as pbar:
		#update progress bar with already downloaded subs
		pbar.update(len(completed_urls))
		
		for i in range(len(to_download_urls)):
			#download subtitle
			to_download_url = to_download_urls[i]
			with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
				ytdl.download([to_download_url])
			#check if a subtitle file has been downloaded
			#ExtractorError doesn't work for some reason, it just throws
			#a warning which I can't even catch with warnings.catch_warnings
			files_after = len(get_subtitle_files(subs_folder))
			if len(sub_urls) != files_after:
				sub_urls.append(to_download_url)
				f.write(f'{to_download_url}\t{titles_dict[to_download_url]}\n')
			#
			pbar.update(1)
			

def CompileSubsText(subs_folder, urls_file, compiled_subs_txtfile):
	
	#create download folder in the folder of the python file
	subs_folder = PY_FILEPATH + '/' + subs_folder

	#open file with titles etc. & make dict
	urls, titles, pubdates, durations = read_urls_file(urls_file)
	titles_dict = dict(zip(urls,titles))
	
	#get urls in the compiled-subs.txt file (if quit prematurely)
	if os.path.isfile(compiled_subs_txtfile):
		with open(compiled_subs_txtfile, 'r', encoding='utf-8') as f:
			lines = f.readlines()
			compiled_urls = [line[5:].strip() for line in lines if line[:5] == 'URL: ']
	else:
		compiled_urls = []
	
	#get url and fullpath of the subfiles to be added to compiled-subs.txt
	sub_urls, sub_filepaths = get_subtitle_files(subs_folder)
	to_compile_urls = get_to_be_handled_urls(sub_urls, compiled_urls)
	
	if not to_compile_urls:
		print('No subtitles to compile!')
		return
	
	sub_filepath_dict = dict(zip(sub_urls, sub_filepaths))
	
	#write subs to compile-subs.txt
	with open(compiled_subs_txtfile, 'a', encoding='utf-8') as f, \
		tqdm.tqdm(range(len(to_compile_urls))) as pbar:
		
		#write (remaining) subs to compiled-subs
		for sub_url in to_compile_urls:
			#url and full path of the sub title file
			sfp = sub_filepath_dict[sub_url]
			#find title corresponding to the url
			sub_title = titles_dict[sub_url]
			#write information about the sub file (url, title) to compiled-subs.txt
			f.write(f'URL: {sub_url}\nTITLE: {sub_title}\nSUBTITLES:\n')
			#open subfile into captions
			captions = webvtt.read(sfp)
			#properly format captions and write to compiled-subs.txt
			for j in range(len(captions)):
				#load caption info
				c = captions[j]
				s = c.start
				e = c.end
				t = c.text
				#split text in previous and current part by \n
				curr_prev = t.split('\n')
				if len(curr_prev) == 2:
					#remove end of line and double spaces
					t = curr_prev[1]
					t = re.sub('\\n', ' ', t)
					t = re.sub('\s\s', '', t)
					t = t.strip()
					#print the text, except for empty text.
					if t not in [' '*i for i in range(2)]:
						#write to compiled-subs.txt
						f.write(f'{s} {e} {t}\n')
			f.write('\n')
			pbar.update(1)


if __name__ == '__main__':

	print('\nFetching URLs...')
	channel_url = sys.argv[1]
	c = ChannelUploads(channel_url)
	
	channel_id = c.channel_id
	subs_folder = channel_id
	urls_file = f'{channel_id}.txt'
	no_subs_file = f'no-subs-{channel_id}.txt'
	
	print('\nDownloading subtitles...\n')

	DownloadSubtitles(subs_folder, urls_file, no_subs_file)
	
	print('\nCompiling subtitles...\n')
	compiled_subs_txtfile = f'compiled-{channel_id}.txt'
	CompileSubsText(subs_folder, urls_file, compiled_subs_txtfile)