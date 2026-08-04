"""Minimal WhatsApp-HTML-export fixtures mirroring the real archive markup.

Kept tiny and self-contained so the archive tests never depend on the 452MB
WhatsApp_All_Chats.zip (which is not committed).
"""

# A date-separator block + inbound/outbound text + an inbound audio + an inbound
# image with a caption + an inline emoji img (must NOT be treated as media) + a
# system/encryption notice (must be SYSTEM_EVENT) + an empty message.
CONV_HTML = """<html><head><meta charset="utf-8"></head><body>
<div class="__vW7d1"><div class="___3_7SH ___3DFk6 __message-out __dark">
<span class="__tail-container"></span>
<div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text">Messages and calls are end-to-end encrypted.</span></div>
</div></div>
<div class="__vW7d1 ___3rjxZ"><div class="___3_7SH __Zq3Mc"><span dir="auto" class="">29/05/2026</span></div></div>
<div class="__vW7d1" id=AAAA1111><div class="___3_7SH __message-in __tail __dark">
<div class="__Tkt2p"><div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text">how much this</span></div>
<div class="___2f-RV"><div class="___1DZAH"><span class="___3EFt_">14:43</span></div></div></div>
</div></div>
<div class="__vW7d1" id=AAAA2222><div class="___3_7SH __message-in __dark">
<div class="__Tkt2p"><div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text">best price??</span></div>
<div class="___2f-RV"><div class="___1DZAH"><span class="___3EFt_">14:44</span></div></div></div>
</div></div>
<div class="__vW7d1" id=BBBB1111><div class="___3_7SH __message-out __dark">
<div class="__Tkt2p"><div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text">we dont do repairs</span></div>
<div class="___2f-RV"><div class="___1DZAH"><span class="___3EFt_">15:00</span></div></div></div>
</div></div>
<div class="__vW7d1" id=CCCC1111><div class="___3_7SH __message-in __dark">
<div class="___2N_Df"><div class="___2jfIu"><audio controls src="2026_05_29_150500_CCCC1111.oga"></audio></div>
<div class="___3Lj_s_in"><div class="___1DZAH"><span class="___3EFt_">15:05</span></div></div></div>
</div></div>
<div class="__vW7d1" id=DDDD1111><div class="___3_7SH __message-in __dark">
<div class="__KYpDv"><img src="2026_05_29_151000_DDDD1111.jpeg" class="x"></div>
<div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text">need repair on this 👞</span></div>
<div class="___2f-RV"><div class="___1DZAH"><span class="___3EFt_">15:10</span></div></div>
</div></div>
<div class="__vW7d1" id=EEEE1111><div class="___3_7SH __message-out __dark">
<div class="__Tkt2p"><div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text">Here is our price list <img alt="🧺" src="../imgs/emoji/basket.png"></span></div>
<div class="___2f-RV"><div class="___1DZAH"><span class="___3EFt_">15:12</span></div></div></div>
</div></div>
<div class="__vW7d1" id=FFFF1111><div class="___3_7SH __message-in __dark">
<div class="__Tkt2p"><div class="___3zb-j"><span dir="ltr" class="__selectable-text __invisible-space __copyable-text"></span></div>
<div class="___2f-RV"><div class="___1DZAH"><span class="___3EFt_">15:13</span></div></div></div>
</div></div>
</body></html>"""

# A near-duplicate of CONV_HTML's inbound content (same customer, same inbound
# text/timestamps) used to test dedup.
CONV_HTML_DUP = CONV_HTML
