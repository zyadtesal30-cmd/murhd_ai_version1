# -*- coding: utf-8 -*-
"""شاشات: ٦) الإعدادات  ٧) المساعد المحلي"""
import copy
import json

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout

import assistant
import engine as E
import ui as UI
from ui import (BG, CARD2, GREEN, MUTED, PICK_BG, PRIMARY, RED, RED_BG, SURFACE, TEXT, ALabel, ArInput, Btn, Card,
                chips, choice_popup, confirm_popup, hrow, info_popup, page, seg, toggle)

TAB_NAMES = [('0', 'بياناتي'), ('1', 'موادي'), ('2', 'حالتي'), ('3', 'القسم'), ('4', 'تسجيل'), ('5', 'خطتي')]
FONT_OPTS = [('0.9', 'صغير'), ('1.0', 'عادي'), ('1.2', 'كبير'), ('1.35', 'كبير جداً')]
CHAT_KEEP = 40


def _sec(text, color=None):
    return ALabel(text, size=16, bold=True, color=color or (0.95, 0.77, 0.3, 1))


class TabsC:
    # ───────────── إعدادات التطبيق ─────────────
    def app_cfg(self):
        a = self.set.get('app')
        if not isinstance(a, dict):
            a = self.set['app'] = dict(E.APP_DEFAULT)
        for k, v in E.APP_DEFAULT.items():
            a.setdefault(k, v)
        return a

    def aset(self, k, v):
        self.app_cfg()[k] = v
        self.schedule_save()

    def apply_app_settings(self):
        a = self.app_cfg()
        UI.set_font_scale(a['font'])
        UI.set_anim(a['anim'])

    def apply_header(self):
        b = getattr(self, 'ab_btn', None)
        if b is None:
            return
        on = bool(self.app_cfg()['chat_on'])
        b.opacity = 1 if on else 0
        b.disabled = not on
        b.width = dp(64) if on else 0

    def t_settings(self, box):
        a = self.app_cfg()

        c = Card()
        c.add_widget(_sec('المظهر'))
        c.add_widget(ALabel('حجم الخط', size=13, color=MUTED))

        def set_font(k):
            self.aset('font', float(k))
            UI.set_font_scale(float(k))
            self.show_tab(6)
        c.add_widget(seg(FONT_OPTS, str(float(a['font'])), set_font))
        c.add_widget(ALabel('الترويسة والتنقل بياخدوا الحجم الجديد بعد إعادة فتح التطبيق.', size=11, color=MUTED))

        def set_anim(v):
            self.aset('anim', bool(v))
            UI.set_anim(bool(v))
        c.add_widget(toggle('حركات وانتقالات ناعمة', a['anim'], set_anim))
        box.add_widget(c)

        c = Card()
        c.add_widget(_sec('بداية التطبيق'))
        c.add_widget(toggle('فتح الدليل لما التطبيق يشتغل', a['guide'], lambda v: self.aset('guide', bool(v))))
        names = dict(TAB_NAMES)
        b = Btn('تبويب البداية: %s   ▼' % names.get(str(a['start_tab']), 'بياناتي'), bg=CARD2, h=46)

        def pick(k):
            self.aset('start_tab', int(k))
            self.show_tab(6)
        b.bind(on_release=lambda *x: choice_popup('تبويب البداية', TAB_NAMES, pick, size=(0.8, 0.6)))
        c.add_widget(b)
        box.add_widget(c)

        c = Card()
        c.add_widget(_sec('المساعد المحلي'))
        c.add_widget(ALabel('بيشتغل بدون إنترنت وبياناتك ما بتخرجش من الجهاز.', size=12, color=MUTED))

        def chat_on(v):
            self.aset('chat_on', bool(v))
            self.apply_header()
        c.add_widget(toggle('إظهار زر «مساعد» في الأعلى', a['chat_on'], chat_on))

        def keep(v):
            self.aset('chat_save', bool(v))
            if not v:
                self.set['chat'] = []
        c.add_widget(toggle('حفظ سجل المحادثة على الجهاز', a['chat_save'], keep))
        r = Btn('فتح المساعد', bg=PRIMARY, h=44)
        r.bind(on_release=lambda *x: self.show_tab(7, top=True))
        d = Btn('مسح سجل المحادثة', bg=CARD2, h=44)
        d.bind(on_release=lambda *x: confirm_popup('تأكيد', 'مسح كل المحادثات؟', self.clear_chat))
        c.add_widget(hrow(d, r, h=44))
        box.add_widget(c)

        c = Card()
        c.add_widget(_sec('بياناتي'))
        b1 = Btn('نسخ احتياطي (نسخ بياناتي للحافظة)', bg=CARD2, h=46)
        b1.bind(on_release=lambda *x: self.copy_text(json.dumps(self.project_data(), ensure_ascii=False)))
        b2 = Btn('استرجاع من الحافظة', bg=CARD2, h=46)
        b2.bind(on_release=lambda *x: confirm_popup('استرجاع', 'هيستبدل بياناتك الحالية بالنسخة اللي في الحافظة. تكمّل؟',
                                                    self.restore_clipboard))
        b3 = Btn('مسح كل بياناتي', bg=RED_BG, fg=RED, h=46)
        b3.bind(on_release=lambda *x: confirm_popup('تأكيد', 'هيتمسح كل المقررات والإعدادات والمحادثات. متأكد؟', self.wipe_all))
        c.add_widget(b1)
        c.add_widget(b2)
        c.add_widget(b3)
        box.add_widget(c)

        c = Card()
        c.add_widget(_sec('أخرى'))
        b4 = Btn('استعادة إعدادات التطبيق الافتراضية', bg=CARD2, h=46)
        b4.bind(on_release=lambda *x: self.reset_app_settings())
        c.add_widget(b4)
        c.add_widget(ALabel('%s\nالمطوّر: %s • الإصدار 2.1' % (E.APP_TITLE, E.DEVELOPER), size=11, color=MUTED, halign='center'))
        box.add_widget(c)

    def reset_app_settings(self):
        self.set['app'] = dict(E.APP_DEFAULT)
        self.apply_app_settings()
        self.apply_header()
        self.schedule_save()
        self.show_tab(6)

    def restore_clipboard(self):
        try:
            d = json.loads(Clipboard.paste())
            if not isinstance(d, dict) or 'rec' not in d:
                raise ValueError('not a backup')
            keep = dict(self.app_cfg())
            self.load_data(d)
            self.set['app'] = keep
            self.load_chat()
            self.changed()
            self.show_tab(0, top=True)
            info_popup('تم', 'اتسترجعت بياناتك ✔', size=(0.8, 0.25))
        except Exception:      # noqa
            info_popup('تعذّر الاسترجاع', 'الحافظة مفيهاش نسخة احتياطية صحيحة. انسخ النسخة الأول وحاول تاني.', size=(0.85, 0.3))

    def wipe_all(self):
        keep = dict(self.app_cfg())
        self.rec = {}
        self.set = copy.deepcopy(E.DEFAULT_SET)
        self.set['app'] = keep
        self.chat = []
        self.dept_sel = set()
        self.changed()
        self.show_tab(0, top=True)

    # ───────────── المساعد المحلي ─────────────
    def load_chat(self):
        out = []
        for x in (self.set.get('chat') or []):
            if isinstance(x, (list, tuple)) and len(x) == 2 and x[0] in ('u', 'a'):
                out.append((x[0], str(x[1])))
        self.chat = out[-CHAT_KEEP:]

    def clear_chat(self):
        self.chat = []
        self.set['chat'] = []
        self.schedule_save()
        if self.tab == 7:
            self.show_tab(7)

    def _persist_chat(self):
        self.set['chat'] = [list(x) for x in self.chat[-CHAT_KEEP:]] if self.app_cfg()['chat_save'] else []
        self.schedule_save()

    def bubble(self, role, text):
        you = role == 'u'
        card = Card(bg=PICK_BG if you else SURFACE, accent=PRIMARY if you else None, pad=12, spacing=2,
                    size_hint_x=0.86)
        card.add_widget(ALabel(text, size=13.5, color=TEXT))
        sp = BoxLayout(size_hint_x=0.14)
        row = BoxLayout(orientation='horizontal', size_hint_y=None, spacing=dp(0))
        row.bind(minimum_height=row.setter('height'))
        if you:         # رسالتك يمين
            row.add_widget(sp)
            row.add_widget(card)
        else:           # رد المساعد شمال
            row.add_widget(card)
            row.add_widget(sp)
        self._chat_box.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self._chat_sv, 'scroll_y', 0), 0.15)

    def set_chat_chips(self, items):
        self._chat_chips.clear_widgets()
        items = [(s, s) for s in items]
        if items:
            self._chat_chips.add_widget(chips(items, None, lambda k: self.chat_send(k), h=36))

    def t_chat(self, root):
        self._chat_sv, self._chat_box = page(pad=12, spacing=10)
        top = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), padding=[dp(12), dp(6), dp(12), 0], spacing=dp(8))
        clr = Btn('مسح', bg=CARD2, fg=MUTED, size=12, h=34, size_hint_x=None, width=dp(64), pos_hint={'center_y': .5})
        clr.bind(on_release=lambda *a: confirm_popup('تأكيد', 'مسح المحادثة؟', self.clear_chat))
        top.add_widget(clr)
        top.add_widget(ALabel('المساعد المحلي — شغّال بدون إنترنت', size=13, bold=True, color=GREEN, pos_hint={'center_y': .5}))
        root.add_widget(top)
        root.add_widget(self._chat_sv)
        self._chat_chips = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(44), padding=[dp(10), 0, dp(10), dp(4)])
        root.add_widget(self._chat_chips)

        typed = {'v': ''}
        q = ArInput(hint='اسأل المساعد…', on_text=lambda v: typed.__setitem__('v', v))

        def send(*a):
            t = typed['v'].strip()
            if not t:
                return
            q.ti.text = ''
            typed['v'] = ''
            self.chat_send(t)
        go = Btn('إرسال', bg=PRIMARY, size=13, h=46, size_hint_x=None, width=dp(76))
        go.bind(on_release=send)
        q.ti.bind(on_text_validate=send)
        bar = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(66), padding=[dp(10), dp(6), dp(10), dp(8)])
        bar.add_widget(hrow(go, q, h=46))
        root.add_widget(bar)

        if not self.chat:
            self.bubble('a', 'أهلاً! أنا مساعدك الأكاديمي المحلي 👋\nبجاوب من بياناتك ولائحة القسم من غير إنترنت. جرّب تسألني عن معدلك أو خطتك أو أي مادة.')
        for role, text in self.chat[-CHAT_KEEP:]:
            self.bubble(role, text)
        self.set_chat_chips(assistant.SUGGEST)

    def chat_send(self, text):
        text = str(text).strip()
        if not text:
            return
        self.chat.append(('u', text))
        if self.tab == 7:
            self.bubble('u', text)

        def cb(p):
            try:
                ans, sug = assistant.answer(text, p)
            except Exception:      # noqa
                ans, sug = 'حصل خطأ وأنا بحاول أجاوب. جرّب صياغة تانية.', assistant.SUGGEST
            self.chat.append(('a', ans))
            self._persist_chat()
            if self.tab == 7:
                self.bubble('a', ans)
                self.set_chat_chips(sug or assistant.SUGGEST)
        self.with_pack(cb)
