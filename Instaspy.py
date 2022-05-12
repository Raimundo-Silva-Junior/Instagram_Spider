from requests import Session
#from requests_html import HTMLSession
from requests.cookies import RequestsCookieJar
from bs4 import BeautifulSoup
import json
import pickle
import os

from datetime import datetime
from getpass import getpass  


class PostSpider:

    def __init__(self):
        
        self.BASE_URL = "https://www.instagram.com/"
        self.LOGIN_URL = "accounts/login/ajax/"
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
        self.LOGIN_URL = f"{self.BASE_URL}{self.LOGIN_URL}"
        
        self.session = Session()
        self.session.headers = {'User-Agent': self.USER_AGENT}
        self.session.headers.update({"Referer": self.BASE_URL})
    
    def login(self, username:str=None, password:str=None, load_cookies:RequestsCookieJar=None, save_cookies:bool=False) -> bool:
        
        if (username == None or password == None) and load_cookies == False:
            raise ValueError("Insert username/password or load cookies.")
        elif save_cookies == True and load_cookies == True:
            raise ValueError("You can't load and save a cookie at the same time.")
        elif (username != None and password != None) and load_cookies == True:
            raise ValueError("You can't login and load credentials at the same time.")
        
        elif isinstance(load_cookies, RequestsCookieJar):
            request = self.session.get(self.BASE_URL)
            self.session.cookies = load_cookies
            
            response = True
            
        else:
            time = int(datetime.now().timestamp())
            login_data = {"username": username,
                "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{time}:{password}",
                "queryParams": "{}",
                "optIntoOneTap": "false",
                "stopDeletionNonce": "",
                "trustedDeviceRecords": "{}" 
            }
            
            request = self.session.get(self.BASE_URL)
            self.session.headers.update({"X-CSRFToken": request.cookies["csrftoken"]})
            
            login = self.session.post(self.LOGIN_URL , data=login_data)
            self.session.headers.update({"X-CSRFToken": request.cookies["csrftoken"]})
            cookies = login.cookies
            
            json_data = json.loads(login.text)
            if json_data["authenticated"]:
                if save_cookies:
                    with open('cookies.pkl','wb') as file:
                        pickle.dump(cookies, file)
                response = True
            else:
                response = False
        return response
    
    def post_data(self, post_link:str) -> dict:
        
        request = self.session.get(post_link)
        url_addicional = post_link[len(self.BASE_URL) -1:]
        html = request.content
        self.soup = BeautifulSoup(html, 'html.parser')
        
        data = self.soup.find_all('script', type="text/javascript")
        json_data = json.loads(data[14].text[len(f"window.__additionalDataLoaded('{url_addicional}',"):-2])
            
        return json_data
    
    def caption(self, json_data: dict) -> str:
        return json_data["items"][0]['caption']['text']
        
    def number_likes(self, json_data:json) -> int:
        return json_data["items"][0]['like_count']
        
    def number_comments(self, json_data:json) -> int:
        return json_data["items"][0]['comment_count']
    
    def content(self, json_data:json, download:bool=False) -> dict:
        
        try:
            if json_data["items"][0]["media_type"] == 0:
                videos = json_data["items"][0]['video_versions'][0]['url']
            else:
                videos = json_data["items"][0]["carousel_media"]
                videos = [video['video_versions'][0]['url'] for video in videos]
            
            if download:
                for index, video in enumerate(videos, start=1):
                    video_data = self.session.get(video)
                    with open(r'.\vid-{0}.mp4'.format(index), 'wb') as file:
                        file.write(video_data.content)
        
        except KeyError:
            
            videos = "Não há video no post!"
            
        finally:
            
            if json_data["items"][0]["media_type"] == 0:
                images = list(json_data["items"][0]['image_versions2']['candidates'][0]['url'])
            else:
                images = json_data["items"][0]["carousel_media"]
                
                images = [image['image_versions2']['candidates'][0]['url'] for image in images]
            
            if download:
                for index, image in enumerate(images, start=1):
                    image_data = self.session.get(image)
                    with open(f'.\img-{index}.jpg', 'wb') as file:
                        file.write(image_data.content)
                
            return {"images": images, "videos":videos}


class ProfileSpider(PostSpider):
    def __init__(self):
        
        super().__init__()
        self.session = Session()
        
        self.QUERY_HASH = "8c2a529969ee035a5063f2fc8602a0fd"
        self.INSTAGRAM_QUERY_LINK = "https://www.instagram.com/graphql/query/?"
        
        self.session.headers = {'User-Agent': self.USER_AGENT}
        self.session.headers.update({"Referer": self.BASE_URL})
        
        
    def login(self, username:str=None, password:str=None, load_cookies:RequestsCookieJar=None, save_cookies:bool=False) -> bool:
        
        super().login(username, password, load_cookies, save_cookies)
    
    def profile_data(self, page_username) -> dict:
        
        instagram_url = f"{self.BASE_URL}{page_username}/"

        with self.session.get(instagram_url) as response:
            soup = BeautifulSoup(response.content, "html.parser")
            scripts = soup.find_all("script", type="text/javascript")
            wanted_script = "window._sharedData = "
            for script in scripts:
                if wanted_script in script.text:
                    script = script.text[len(wanted_script):-1]
                    script = json.loads(script)
                    break 
                
            biography = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["biography"]
            followed = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_followed_by"]["count"]
            following = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_follow"]["count"]
            id = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["id"]
            category_name = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["category_name"]
            username = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["username"]
            publications = script["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_owner_to_timeline_media"]["count"]
 
        
        return {"username": username, "id": id, "biography": biography, "publications" :publications,
                "followed": followed, "following": following, "category_name": category_name}
        
    def get_posts_links(self, id: str, quantity: int) -> list:
        
        query_data = {"query_hash": self.QUERY_HASH, "variables":{"id":id,"first":12}}
        query_data_str = json.dumps(query_data)
        index = query_data_str.index("{", 1)
        variables = query_data_str[index: -1]
        variables = variables.replace(":", "%3A")
        variables = variables.replace(",", "%2C")
        variables = variables.replace(" ", "")

        instagram_posts_link = f'{self.INSTAGRAM_QUERY_LINK}query_hash={query_data["query_hash"]}&variables={variables}'

        post_links = []
        post_likes = []
        post_comments = []
        post_views = []
        post_captions = []
        
        not_new_link = False
        
        while True:
        
            with self.session.get(instagram_posts_link) as response:
                
                data = response.json()

                data_sources = data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
                
                for data_source in data_sources:
                    link = f'{self.BASE_URL}p/{data_source["node"]["shortcode"]}/'
                    comments = data_source["node"]["edge_media_to_comment"]["count"]
                    likes = data_source["node"]["edge_media_preview_like"]["count"]
                    try:
                        caption = data_source["node"]["edge_media_to_caption"]["edges"][0]["node"]["text"]
                    except IndexError:
                        caption = " "
                    
                    
                    if data_source["node"]["is_video"] == True:
                        views = data_source["node"]["video_view_count"]
                    else:
                        views = " "
                        
                    if link not in post_links:
                        post_links.append(link)
                        post_comments.append(comments)
                        post_likes.append(likes)
                        post_views.append(views)
                        post_captions.append(caption)
                    else:
                        not_new_link = True
                        break
                        
                        
                end_link = data["data"]["user"]["edge_owner_to_timeline_media"]["page_info"]["end_cursor"]    
                instagram_posts_link = instagram_posts_link[:-1] + f'%2C"after"%3A"{end_link}"' + "}"  
                     
            if len(post_links) >= quantity or not_new_link:
                break
 
        return [{"link": link, "likes": likes, "comments": comments, "views": views, "caption": caption} for 
                link, likes, comments, views, caption in zip(post_links[:quantity], post_likes[:quantity], post_comments[:quantity],
                                                             post_views[:quantity], post_captions[:quantity])]
        
        
if __name__ == "__main__":
    
    if os.path.exists('.\cookies.pkl'):
        with open('.\cookies.pkl',"rb") as file:
            cookies = pickle.load(file)
            
        # link = "https://www.instagram.com/p/CaKMBueM7Rm/"
        # spider = PostSpider()
        # login = spider.login(load_cookies=cookies)  
        
        # data = spider.post_data(link)
        
        # title = spider.title(data)
        # number_likes = spider.number_likes(data)
        # number_comments = spider.number_comments(data)
        
        # print()
        # print(f'Title:\n{title}')
        # print()
        # print(f'Likes:\n{number_likes}')
        # print()
        # print(f'Comments:\n{number_comments}')
        # spider.content(data, download=True)
        
        page = "deusogrego"
        spider = ProfileSpider()
        spider.login(load_cookies=cookies)
        data = spider.profile_data(page)
        id = data["id"]
        print(data)    
        data = spider.get_posts_links(id, 100)
        spider.session.close()
        print(data)
            
    else:
        link = "https://www.instagram.com/p/CaKMBueM7Rm/"
        spider = PostSpider()
        username = input("\nUsername: ")
        password = getpass("\nPassword: ")
        login = spider.login(username=username, password=password, save_cookies=True)  
        if login:
            data = spider.post_data(link)
            
            title = spider.title(data)
            number_likes = spider.number_likes(data)
            number_comments = spider.number_comments(data)
            
            print()
            print(f'Title:\n{title}')
            print()
            print(f'Likes:\n{number_likes}')
            print()
            print(f'Comments:\n{number_comments}')
            
        else:
            print()
            print("User not autenticated!")
    
    pass
    