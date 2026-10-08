import os #Using command prompt to import all libraries on its own for once in the starting
import sys #To open the graphing window
import subprocess #To run command prompts and open other files
import importlib.util # Check if the module exists
import urllib.parse #pass the math expressions to wolfram alpha 
import warnings #to stop pygame warning message in the shell
warnings.filterwarnings("ignore", category=UserWarning)
auto_expr = None
if len(sys.argv) > 1:
    auto_expr = sys.argv[1]


BOOT_FILE = ".picore_bootstrapped"

REQUIRED = {
    "pygame": "pygame",
    "requests": "requests",
    "mysql": "mysql-connector-python"
}


def ensure(pkg, pip_name): #Command prompt cursor function that downloads the required module when called
    if importlib.util.find_spec(pkg) is None: #Checks already installed modules
        subprocess.call(
            [sys.executable, "-m", "pip", "install", pip_name], #installs it silently without opening shell
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

if not os.path.exists(BOOT_FILE):  #to check this is the first time we are running this code
    for m, p in REQUIRED.items():
        ensure(m, p)
    with open(BOOT_FILE, "w") as f:
        f.write("done")

# PYGAME IS IMPORTED

import pygame
import requests #to connect with wolfram over http
pygame.init() #pygame initialized



#-----------ADDING BG MUSIC----------
pygame.mixer.init()
pygame.mixer.music.load('bgmusic.mp3')  #loading music file
pygame.mixer.music.play(-1)  # -1 = loop forever
music_on = True
def stop_music():
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
    music_btn.text = "MUSIC: OFF"


# ---------------- LOADING ----------------
class LoadingScreen: #Classify all the UI buttons while loading the app/ animation
    def __init__(self):
        self.words = ["Consulting Archimedes","Dividing Circles by Zero","Summoning Infinite Series","Arguing with Irrational Numbers","Convincing π to Terminate","Chasing Digits Past Infinity","Proving This Will Eventually Load"]
        self.i = 0 #initial value
        self.t = 0 #text frame counter
        self.font = pygame.font.SysFont(None, 28, bold=True) #font object created (crucial for rendering the objects)

    def update(self): #Runs those frames of texts while loading
        self.t += 1
        if self.t % 60 == 0: #trigger once every 60 frames
            self.i = (self.i + 1) % len(self.words) #move to next message

    def draw(self, s):
        txt = self.font.render(self.words[self.i], True, (180,140,255)) #using the font object to render
        s.blit(txt, txt.get_rect(center=s.get_rect().center)) #centre aligning the text

# ----------------PI CORE WINDOW BEGINSSS----------------
screen = pygame.display.set_mode((1280,720),
    pygame.RESIZABLE | pygame.SCALED | pygame.DOUBLEBUF
)
icon = pygame.image.load("picore_logo.png").convert_alpha() #icon for the pygame window
pygame.display.set_icon(icon)
pygame.display.set_caption("πCore")

bg1 = pygame.image.load("background1.png").convert()
bg2 = pygame.image.load("background2.png").convert()

#backgrounds are scaled ONCE and reused (performance fix, logic unchanged)
def scale_backgrounds():
    global bg_menu, bg_game
    size = screen.get_size()
    bg_menu = pygame.transform.smoothscale(bg1, size)
    bg_game = pygame.transform.smoothscale(bg2, size)

scale_backgrounds()

clock = pygame.time.Clock()
loader = LoadingScreen()
ticks = 0
state = "LOADING"

# ---------------- INPUT CARD UI ---------------
class InputCard: #creating animated UI for the input
    def __init__(self, rel_pos, rel_size):
        self.rel_pos = rel_pos
        self.rel_size = rel_size
        self.rect = pygame.Rect(0,0,0,0) #position and size fixed
        self.text = "" #saving users text
        self.active = False

        self.font = pygame.font.SysFont("segoeui", 22, bold=True) #font object
        self.icon = pygame.font.SysFont("segoeui", 40, bold=True) #Epsilon LOGO
        self.cursor_visible = True #cursor blinking animation
        self.cursor_timer = 0 #timer for cursor toggle

    def resize(self, size): #while resizing the window, the button should stay in tact
        w,h = size #window dimensions
        cw = int(self.rel_size[0]*w) # computing the new coords
        ch = int(self.rel_size[1]*h)
        cx = int(self.rel_pos[0]*w - cw//2)
        cy = int(self.rel_pos[1]*h - ch//2)
        self.rect = pygame.Rect(cx,cy,cw,ch)#updates the box

    def update(self): #cursor blinking function
        if self.active:
            self.cursor_timer += clock.get_time() #time-based blinking (same speed, smoother)
            if self.cursor_timer > 500: #blink every 0.5 seconds
                self.cursor_visible = not self.cursor_visible #blink effect
                self.cursor_timer = 0
        else:
            self.cursor_visible = False
            self.cursor_timer = 0

    def draw(self, s): #drawing the UI 
        mouse = pygame.mouse.get_pos()
        hover = self.rect.collidepoint(mouse)

        offset = -6 if hover else 0
        shadow_offset = 18 if hover else 10 

        # shadow layer
        shadow = self.rect.move(shadow_offset, shadow_offset)
        pygame.draw.rect(s, (233,181,11), shadow)

        # main container
        main = self.rect.move(offset, offset)
        pygame.draw.rect(s, (240,240,240), main)
        pygame.draw.rect(s, (0,0,0), main, 4)

        # epsilon icon
        eps = self.icon.render("ε", True, (0,0,0))
        s.blit(eps, (main.x+15, main.centery-20))

        # input field
        inp = pygame.Rect(main.x+70, main.centery-22, main.width-90, 44)
        pygame.draw.rect(s, (255,255,255), inp)
        pygame.draw.rect(s, (0,0,0), inp, 3)

        display_text = self.text
        if self.active and self.cursor_visible:
            display_text += "|"

        txt = display_text if self.text else "Enter Expression"
        col = (0,0,0) if self.text else (120,120,120)
        s.blit(self.font.render(txt, True, col), (inp.x+10, inp.y+10))

# ---------------- BUTTON ----------------
class Button: #button that can be reused
    def __init__(self,text,rel_pos,rel_size): 
        self.text=text
        self.rel_pos=rel_pos
        self.rel_size=rel_size
        self.rect=pygame.Rect(0,0,0,0) #placeholder created
        self.font=pygame.font.SysFont(None,36,bold=True)

    def resize(self,size): #Same Resize Logic
        w,h=size
        bw=int(self.rel_size[0]*w)
        bh=int(self.rel_size[1]*h)
        bx=int(self.rel_pos[0]*w-bw//2)
        by=int(self.rel_pos[1]*h-bh//2)
        self.rect=pygame.Rect(bx,by,bw,bh) #resized rectangle 

    def draw(self,s):
        hover=self.rect.collidepoint(pygame.mouse.get_pos()) #detects hovering
        off=(-2,-2) if hover else (0,0)
        sh=(6,6) if hover else (4,4) #animations of hovering

        pygame.draw.rect(s,(0,0,0),self.rect.move(sh))
        pygame.draw.rect(s,(251,202,31),self.rect.move(off)) #shadow effect
        pygame.draw.rect(s,(0,0,0),self.rect.move(off),3)

        t=self.font.render(self.text,True,(0,0,0))
        s.blit(t,t.get_rect(center=self.rect.move(off).center)) #centres and draws the text

    def clicked(self,e): #detects clicks
        return e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and self.rect.collidepoint(e.pos) 

# ---------------- UI ELEMENTS MAPPED TO THEIR CLASS----------------
input_card = InputCard((0.5,0.35),(0.45,0.22)) #real position and size initialized
enter_btn  = Button("ENTER",(0.5,0.7),(0.18,0.08))
graph_btn  = Button("GRAPH",(0.85,0.35),(0.12,0.07))
back_btn   = Button("BACK",(0.08,0.08),(0.1,0.06))
music_btn  = Button("MUSIC: ON",(0.92,0.94),(0.16,0.07))
history_btn = Button("HISTORY",(0.85,0.45),(0.12,0.07))

for b in (enter_btn, graph_btn, back_btn, music_btn, history_btn):
    b.resize(screen.get_size())

input_card.resize(screen.get_size())

# ---------------- WOLFRAM ----------------
WA_APP_ID = "REDACTED"  # key moved to picore.config.json

def normalize(q):
    q=q.strip()
    if " and " in q and "=" in q:
        q="solve "+q
    return q

def evaluate(q):
    url="https://api.wolframalpha.com/v2/query"
    params={"appid":WA_APP_ID,"input":q,"output":"json"}
    r=requests.get(url,params=params,timeout=10)
    pods=r.json().get("queryresult",{}).get("pods",[])
    res=[]
    for p in pods:
        txt=[s["plaintext"] for s in p.get("subpods",[]) if s.get("plaintext")]
        if txt:
            res.append((p.get("title",""),"\n".join(txt)))
    return res if res else [("Error","No result")]

# ---------------- RESULT BOXES FOR WOLFRAM RESULTS ----------------
def wrap_text(text, font, max_width):
    # normalize Wolfram whitespace
    text = text.replace("\xa0", " ").replace("\n", " ")

    words = text.split()
    lines = []
    current = ""

    for w in words:
        test = current + w + " "
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w + " "

    if current:
        lines.append(current)

    # absolute safety: never return empty
    if not lines:
        lines = ["[unrenderable text]"]

    return lines

class ResultView:
    def __init__(self):
        self.results=[] #store information about the expression 
        self.scroll=0 #vertical scroll
        self.ft = pygame.font.SysFont("segoeui", 22, bold=True) or pygame.font.SysFont(None,22,bold=True)
        self.fb = pygame.font.SysFont("segoeui", 18) or pygame.font.SysFont(None,18)



    def load(self,r): #load the new results
        self.results=r
        self.scroll=0 #reset scroll

    def draw(self, s):
        y = 160 + self.scroll
        mouse = pygame.mouse.get_pos()

        if not self.results:
            debug = self.fb.render("The Clock’s On You.", True, (255, 100, 100))
            s.blit(debug, debug.get_rect(center=(s.get_width()//2, s.get_height()//2)))
            return

        for t, c in self.results:

            # ---- SAFE text handling ----
            try:
                lines = wrap_text(c, self.fb, s.get_width() - 190)
            except Exception:
                lines = [c[:200]]  # absolute fallback

            line_h = self.fb.get_height() + 2
            rect_h = max(80, len(lines)*line_h + 50)
            rect = pygame.Rect(80, y, s.get_width()-160, rect_h)

            hover = rect.collidepoint(mouse)
            off = 5 if hover else 0

            pygame.draw.rect(s, (251,202,31), rect.move(-5,5))
            pygame.draw.rect(s, (0,0,0), rect.move(off,-off))
            pygame.draw.rect(s, (251,202,31), rect.move(off,-off), 3)

            s.blit(self.ft.render(t, True, (255,255,255)),
                   (rect.x+15+off, rect.y+10-off))

            tx = rect.x + 15 + off
            ty = rect.y + 40 - off

            for line in lines:
                if ty + self.fb.get_height() > rect.bottom - 10:
                    break
                s.blit(self.fb.render(line, True, (230,230,230)), (tx, ty))
                ty += line_h

            y += rect_h + 20

result_view = ResultView()
# -------- AUTO-RUN FROM HISTORY --------
if auto_expr:
    expr = auto_expr        
    auto_expr = None
    state = "GAME"


    input_card.text = expr

    res = evaluate(normalize(expr))
    result_view.load(res)

    try:
        from db import save_query
        save_query(expr, res)
    except Exception as e:
        print("DB ERROR (auto-run):", e)



# ---------------- MAIN LOOP ----------------
running=True
while running:
    for e in pygame.event.get(): #Detects if the window is closed
        if e.type==pygame.QUIT:
            running=False

        if e.type==pygame.VIDEORESIZE: #resizing the window and the background stays in tact
            screen=pygame.display.set_mode(
                e.size,
                pygame.RESIZABLE | pygame.SCALED | pygame.DOUBLEBUF
            )
            scale_backgrounds() #rescales the bg safely
            for b in (enter_btn, graph_btn, back_btn, music_btn, history_btn):
                b.resize(e.size)
            input_card.resize(e.size)

            music_btn.resize(e.size)

        if state=="MENU" and enter_btn.clicked(e):  #if we click the background, the new bg appears
            state="GAME"

        if state=="GAME" and back_btn.clicked(e): #if back button is clicked, reset game state,inputs,results and change bg
            state="MENU"
            input_card.text=""
            input_card.active=False
            result_view.results.clear()

        if state=="GAME" and graph_btn.clicked(e):#if graph button is clicked, then send signal to open graph 
            if input_card.text.strip(): #ensures no empty input is sent
                plot_q = input_card.text.strip() #formatted query for wolfram alpha
                enc = urllib.parse.quote_plus(plot_q) #Encodes our expression before sending it to the graphing window
                subprocess.Popen([sys.executable,"graph_window.py",enc]) #Sys module helps open Graphing window
#without freezing main file
        if state == "GAME" and history_btn.clicked(e):
            stop_music()
            subprocess.Popen(
                [sys.executable, "history_window.py"],
                cwd=os.path.dirname(__file__)
            )



        if state=="GAME" and e.type==pygame.MOUSEBUTTONDOWN:  #if mouse button is clicked
            input_card.active=input_card.rect.collidepoint(e.pos) #only if it is clicked inside the buttons

        if music_btn.clicked(e): #music button if clicked
            if music_on: 
                pygame.mixer.music.pause()
                music_btn.text = "MUSIC: OFF"
                music_on = False
            else:
                pygame.mixer.music.unpause()
                music_btn.text = "MUSIC: ON"
                music_on = True

        if state=="GAME" and e.type==pygame.MOUSEWHEEL: #if scrolled 
            result_view.scroll+=e.y*20  #scroll up and down respectively

        if state=="GAME" and e.type==pygame.KEYDOWN:
            if e.key == pygame.K_RETURN and input_card.text.strip():
                res = evaluate(normalize(input_card.text))
                result_view.load(res)

                try:
                    from db import save_query
                    save_query(input_card.text.strip(), res)
                except Exception as e:
                    print("DB ERROR:", e)

            elif input_card.active:
                if e.key == pygame.K_BACKSPACE:
                    input_card.text = input_card.text[:-1]
                else:
                    input_card.text += e.unicode


            elif e.key==pygame.K_BACKSPACE:
                input_card.text=input_card.text[:-1] #deletes if backspace
            else:
                input_card.text+=e.unicode #appends the typed character

    screen.blit(bg_menu if state=="MENU" else bg_game,(0,0)) #renders bg

    if state=="LOADING": #loading screen logic
        loader.update()
        loader.draw(screen)
        ticks+=1
        if ticks>430: #ticks for 2 seconds
            state="MENU" #loads menu after ticking

    elif state=="MENU":
        enter_btn.draw(screen) #renders enter button 

    elif state=="GAME": #main app screen
        back_btn.draw(screen) #back button
        graph_btn.draw(screen) #graph button
        history_btn.draw(screen)  #history button
        input_card.update()  #input card resets
        input_card.draw(screen) #input card 
        result_view.draw(screen) #results 

    music_btn.draw(screen)
    pygame.display.flip() #pushes rendered frame to screen
    clock.tick(60) #sticks to 60FPS

pygame.quit() #if main loop ends, close the initialization
