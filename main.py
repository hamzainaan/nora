"""
    Nora, A Basic Discord Bot to support coinflip, slot and some moderation stuff.
    Copyright (C) 2022  Hamza Inan <h@inanweb.ml>

    Nora is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Nora is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

#Gerekli Kütüphaneler
import discord
from discord.ext import commands
from cryptography.fernet import Fernet
import sqlite3
import random
import asyncio
import time

#Bakiye manipülasyonu için şifreleme.
#Buraya, manipülasyonu yapacak kişinin Discord ID'si girilmeli.
admin = "ADMIN-ID"
gen_key = Fernet.generate_key()
fernet = Fernet(gen_key)
sifreli_id = fernet.encrypt(str(admin).encode())

#Kullanıcı verilerinin tutulduğu database
db = sqlite3.connect("userdata.db")
selector = db.cursor()

#Botu tüm intents'ler ile kuruyoruz.
#Prefixi istediğiniz gibi ayarlayabilirsiniz.
intents = discord.Intents.all()
client = commands.Bot(command_prefix="n", intents=intents)

#İlk etapta bu kod bloğu çalışacaktır. 
#Yukarıda belirttiğimiz isimli veritabanı bulamazsa aynı klasörde üretecektir.
selector.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, cash INTEGER)''')

#Günlük bakiye.
async def free():
    selector.execute('''SELECT * FROM users''')
    data = selector.fetchall()

    #Her kullanıcıyı itere et.
    for i in data:
        selector.execute("UPDATE users SET cash = cash + 500 WHERE id = ?", (i[0],))
        db.commit()

#Her kullanıcıya 24 saatte otomatik +500 para ekleyen bir fonksiyon.
async def auto_add_balance():
    while(True):
        await asyncio.sleep(86400)
        await free()

#Bot başarıyla bağlanırsa bu dönecektir.
@client.event
async def on_ready():

    #Terminale başarıyla bağlandığına dair bir işaret bırakalım.
    print("bip-bop!")

    #Botun davranışını değiştiriyorum. 
    #Bu komut satırı, yazacağınız string'i dinlediği müzik olarak değiştirir.
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Lapsekili Tayfur - Geceler"))

    #Bot aktif olduğundan itibaren her 24 saatte otomatik +500 ekle.
    client.loop.create_task(auto_add_balance())

#Bu metot, sunucuya her yeni üye katıldığında çalışacaktır.
@client.event
async def on_member_join(newbie):

    #Bir mesaj gönderelim.
    await newbie.guild.system_channel.send(f'Katıldığın için teşekkürler sensei {newbie.mention}!')

#Eğer harici komut girilirse botu tetiklemeyi önle.
@client.event
async def on_command_error(ctx, hata):
    if(isinstance(hata,commands.CommandNotFound)): return

#---------------------------------------------------------------------------#
#Aşağıda context kullanarak her bir komut için ayrı ayrı işlevler yazacağız.
#---------------------------------------------------------------------------#

#0. Bakiye Sıfırlama
#Bu komut, mevcut kullanıcının bakiyesini sıfırlar.
#Komut kullanımı: <prefix><r> <@user>
@client.command(name="r",hidden=True)
async def reset_balance(ctx, u: discord.Member):

    #İlgili datayı getiriyoruz.
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id),))
    data = selector.fetchone()

    #Eğer kullanıcı ilk defa bu komutu kullandıysa, verisi olmayacak. Data değeri Null dönecek.
    #Bu durumda kullanıcıya bir kayıt oluşturulacak ve +5000 bakiye yüklenecek.
    if(data is None):
        selector.execute('''INSERT INTO users (id,cash) VALUES (?, 0)''',(str(u.id),))
        db.commit()
        await ctx.send(f'**{u.mention}** kullanıcısının bakiyesi sıfırlandı. <a:onay:1053352128392994846>')
    else:
        selector.execute('''UPDATE users SET cash = 0 WHERE id = ?''',(str(u.id),))
        db.commit()
        await ctx.send(f'**{u.mention}** kullanıcısının bakiyesi sıfırlandı. <a:onay:1053352128392994846>')

#1. Botun kendisini sunucudan şutlaması
#Bu komutu kullandığınızda bot kendisini mevcut sunucudan çıkaracaktır.
#Komut kullanımı: <prefix><kick>
@client.command(name="kick",hidden=True)
async def sunucudan_ayril(ctx):

    #Sunucuyu bilgilendir ve ayrıl.
    await ctx.send(f'Güzel zamanlar için teşekkürler! Ayrılık vaktim geldi :(')
    await ctx.guild.leave()

#2. Gecikme hesabı
#Bu komut kullanıldığında, bot sunucuyla arasındaki gecikmeyi bastıracaktır.
#Komut kullanımı: <prefix><ping>
@client.command(name="ping",brief="Bu komut sayesinde gecikme değerini ölçebilirsiniz. nping yazmanız yeterlidir.")
async def calculate_latency(ctx):

    #Bot kullanıcının mesajına bir emoji ekleyecek ve arada geçen süreyi hesaplayacak.
    #Bunun için iki adet değişken tanımlamak yeterli olacaktır.
    birinci, ikinci = time.monotonic(), 0
    await ctx.message.add_reaction("🏓")
    ikinci = time.monotonic()
    await ctx.send(f'Pong in **{(ikinci-birinci)*100:.2f}** ms.')

#3. Mevcut kanaldaki belirtilen adet kadar mesaj silme
#Bu komut, belirtilen içerik sayısı kadar mesaj silecektir.
#Bunun için ayrıca mesajları yönetme yetkisinin de olması gerekmekte.
#Komut kullanımı: <prefix><t> <value>
@client.command(name="t",brief="Bu komut sayesinde mevcut kanaldaki mesajları silebilirsiniz. nt <silinecek_mesaj_adeti> yazmanız yeterlidir.")
@commands.has_permissions(manage_messages=True)
async def clean_messages(ctx, adet: str):

    #Adet parametresini string alıyoruz çünkü kullanıcı "all" gireiblir.
    #Bu durumda sunucudaki olası tüm mesajları sildireceğiz. (Adet 2000 olarak belirli.)
    #Hareketli onay emoji komutu: <a:onay:1053352128392994846>
    await ctx.channel.purge(limit=(2000) if adet=="all" else int(adet)+1)
    if(adet=="all"):
        await ctx.send(f'Mevcut kanaldaki **tüm** mesajlar temizlendi. <a:onay:1053352128392994846>')
    else:
        await ctx.send(f'Mevcut kanaldaki **{int(adet):,}** adet mesaj temizlendi. <a:onay:1053352128392994846>')

#4. Bakiye kontrolü
#Bu komut, kullanıcılara bakiyelerini döndürür. Veritabanından doğrulama yaparak.
#İlk kayıt olacaklar için +5000 bakiye verecek. Kaydı varsa, mevcut bakiyesini döndürecek.
#Komut kullanımı: <prefix><b>
@client.command(name="b",brief="Bu komut sayesinde bakiyenizi öğrenebilirsiniz. nb yazmanız yeterlidir.")
async def check_balance(ctx):

    #İlgili datayı getiriyoruz.
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id), ))
    data = selector.fetchone()

    #Eğer kullanıcı ilk defa bu komutu kullandıysa, verisi olmayacak. Data değeri Null dönecek.
    #Bu durumda kullanıcıya bir kayıt oluşturulacak ve +5000 bakiye yüklenecek.
    if(data is None):
        selector.execute('''INSERT INTO users (id,cash) VALUES (?, 5000)''',(str(ctx.author.id), ))
        db.commit()
        bakiye = 5000
    else:
        bakiye = data[0]

    #Bakiyeyi yazdırıyoruz.
    await ctx.send(f'Güncel bakiyeniz: **{bakiye:,}** 💵')

#5. Bakiye Manipülasyonu
#Bu komutu kullanacak kişinin ID'si, yukarıda tanımlanmalıdır. Aksi halde çalışmayacak.
#Komut kullanımı: <prefix><sb> <@user> <value>
@client.command(name="sb",hidden=True)
async def change_balance(ctx, u: discord.Member, a: int):

    #Eğer bu mesajı yazan siz değilseniz, çalışmayacak.
    if(ctx.message.author.id != int(fernet.decrypt(sifreli_id).decode())):
        return

    #Eğer sizseniz, bakiyeyi manipüle edebileceksiniz.
    #Kullanıcı kayıtlı değilse, kayıt et ve bakiyeyi manipüle et.
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(u.id),))
    if(selector.fetchone() is None):
        selector.execute('''INSERT INTO users (id,cash) VALUES (?, 0)''',(str(u.id),))
        db.commit()

    #Kullanıcı kayıt edildi, bakiyeyi düzenle ve bildiri mesajı ver.
    selector.execute('''UPDATE users SET cash = cash + ? WHERE id = ?''',(a,str(u.id)))
    db.commit()
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(u.id),))
    data = selector.fetchone()
    await ctx.send(f'{u.mention} kullanıcısının bakiyesi **{data[0]:,}** 💵 olarak güncellendi.')

    #Mesaj bildirimlerini sil.
    await ctx.channel.purge(limit=2)

#6. Yazıtura Implementasyonu
#Bu komut, botun yazıtura oynamasına olanak sağlar.
#Komut kullanımı: <prefix><cf> <h/t> <value>
@client.command(name="cf",brief="Bu komut sayesinde yazıtura oynayabilirsiniz. ncf <h/t> <bahis> yazmanız yeterlidir.")
async def pick_coinflip(ctx, att: str, a: str):

    #Manipülasyondan farkı, kullanıcı ilk defa kullanıp oyunlar oynamak isteyebilir.
    #Bakiyeyi +5000 olarak başlatacağız eğer kullanıcı bulunamadıysa.
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id),))
    data = selector.fetchone()
    if(data is None):
        selector.execute('''INSERT INTO users (id, cash) VALUES (?, 5000)''',(str(ctx.author.id),))
        db.commit()
        bakiye = 5000
    else:
        bakiye = data[0]

    #Şimdi bahis miktarıyla bakiyesini kontrol edeceğiz. Yeterli bakiyesi yoksa oynayamaz.
    tmp = bakiye if(a=="all") else int(a)
    if(tmp>bakiye or bakiye==0):
        await ctx.send(f'Bakiyeniz yetersiz. Bu bahsi yapabilmeniz için **{tmp-bakiye:,}** 💵 daha ihtiyacınız var.')
        return

    #Bahis, bakiyeden az veya bakiyeye eşitse, oyuna devam et.
    #Şimdi, random kullanarak yazı ya da tura seçmesini sağlayacağız.
    sonuc = random.choice(['h','t'])
    inform = await ctx.send(f'Para atılıyor <a:animcoin:1053338774307872820>')

    #Bu kısımda biraz uyutacağız. Animasyon, hemen sonuç göstermesin.
    #ÖNEMLİ: asyncio.sleep fonksiyonunun parametresi saniye cinsindendir.
    await asyncio.sleep(2)

    #Şimdi kazanıp kazanmadığını belirliyoruz. Kazandıysa bakiyesine x2 ekliyoruz. Kaybettiyse bahsini alıyoruz.
    #Kazandıysa;
    if (att[0].lower()==sonuc):
        selector.execute('''UPDATE users SET cash = cash + ? WHERE id = ?''',(tmp,str(ctx.author.id)))
        selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id),))
        data = selector.fetchone()
        await inform.edit(content=f'Kazandın. Güncel bakiyen **{data[0]:,}** 💵')
    #Kaybettiyse;
    else:
        selector.execute('''UPDATE users SET cash = cash - ? WHERE id = ?''',(tmp,str(ctx.author.id)))
        selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id),))
        data = selector.fetchone()
        await inform.edit(content=f'Kaybettin. Güncel bakiyen **{data[0]:,}** 💵') 

#7. Slot Oyunu Implementasyonu
#Bu komut, botun slot oynatmasına olanak sağlar.
#Komut kullanımı: <prefix><s> <value>
@client.command(name="s",brief="Bu komut sayesinde slot oynayabilirsiniz. ns <bahis> yazmanız yeterlidir.")
async def pick_slot(ctx, a: str):

    #Manipülasyondan farkı, kullanıcı ilk defa kullanıp oyunlar oynamak isteyebilir.
    #Bakiyeyi +5000 olarak başlatacağız eğer kullanıcı bulunamadıysa.
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id),))
    data = selector.fetchone()
    if(data is None):
        selector.execute('''INSERT INTO users (id, cash) VALUES (?, 5000)''',(str(ctx.author.id),))
        db.commit()
        bakiye = 5000
    else:
        bakiye = data[0]

    #Şimdi bahis miktarıyla bakiyesini kontrol edeceğiz. Yeterli bakiyesi yoksa oynayamaz.
    tmp = bakiye if(a=="all") else int(a)
    if(tmp>bakiye or bakiye==0):
        await ctx.send(f'Bakiyeniz yetersiz. Bu bahsi yapabilmeniz için **{tmp-bakiye}:,** 💵 daha ihtiyacınız var.')
        return

    #Slot oyunu
    slot_components = ['🚖', "🚢", "🛫", "🚂", "🤙"]
    slot = [random.choice(slot_components) for _ in range(3)]
    inform = await ctx.send(f'Slot dönüyor.\n| <:slot:1053360520993972234> | <:slot:1053360520993972234> | <:slot:1053360520993972234> |')
    await asyncio.sleep(1)
    await inform.edit(content=f'Slot dönüyor..\n| {slot[0]} | <:slot:1053360520993972234> | <:slot:1053360520993972234> |')
    await asyncio.sleep(1)
    await inform.edit(content=f'Slot dönüyor...\n| {slot[0]} | {slot[1]} | <:slot:1053360520993972234> |')
    await asyncio.sleep(1)
    await inform.edit(content=f'Slot dönüyor...\n| {slot[0]} | {slot[1]} | {slot[2]} |')

    #Slot belli oldu. Artık kazandığı ya da kaybettiği tutarı belirlemeliyiz.
    tutar = tmp*10 if(slot[0]==slot[1]==slot[2]) else tmp*2 if(slot[0]==slot[1] or slot[1]==slot[2]) else -tmp
    selector.execute('''UPDATE users SET cash = cash + ? WHERE id = ?''',(tutar,str(ctx.author.id)))
    selector.execute('''SELECT cash FROM users WHERE id = ?''',(str(ctx.author.id),))
    data = selector.fetchone()
    if(tutar>0): await ctx.send(f'**{tutar:,}** 💵 kazandınız! Yeni bakiyeniz: **{data[0]:,}** 💵')
    else: await ctx.send(f'**{tutar:,}** 💵 kaybettiniz! :( Yeni bakiyeniz: **{data[0]:,}** 💵')

#Tüm metotlar tamamlandı. Artık botu çalıştırabiliriz.
#Bunun için botunuzun tokeni gerekmekte.
client.run("BOT-TOKENI")

