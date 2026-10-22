"""Single-entry KIWAD sound replacement with verified backups and atomic commits.

Format references: jonpalmisc/libkiwad SPEC.org; wizspoil/wizwad 4f871ba2.
No game files, offsets, executable patches or archive extraction are required.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import wave
import zlib

MAX_AUDIO = 3 * 1024 * 1024
RECORD = struct.Struct('<lll?Ll')
HURT_HINTS = ('hurt','pain','damage','hit','grunt','wince')


def sound_rows(index, changes, query=''):
    rows=[]
    for name,entry in index.entries.items():
        extension=Path(name).suffix.lower()
        if extension not in ('.wav','.ogg','.mp3') or query.casefold() not in name.casefold():continue
        rows.append({'name':name,'bytes':entry['size'],'format':extension[1:],
                     'changed':name in changes,'candidate':any(s in name.casefold() for s in HURT_HINTS),
                     'label':changes.get(name,{}).get('label','')})
    rows.sort(key=lambda r:(not r['changed'],not r['candidate'],r['name'].casefold()))
    return rows

class SoundError(ValueError):
    pass


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(4*1024*1024),b''):h.update(data)
    return h.hexdigest()


def ki_crc(data):
    return zlib.crc32(data,0xffffffff)^0xffffffff


def json_save(path,value):
    tmp=path.with_suffix('.tmp')
    with open(tmp,'w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def ogg_crc(data):
    crc=0
    for b in data:
        crc^=b<<24
        for _ in range(8):crc=((crc<<1)^0x04c11db7 if crc&0x80000000 else crc<<1)&0xffffffff
    return crc


def audio_info(data,extension):
    if not 32<=len(data)<=MAX_AUDIO:raise SoundError('Sound muss zwischen 32 Bytes und 3 MB groß sein.')
    if extension=='.wav':
        if data[:4]!=b'RIFF' or data[8:12]!=b'WAVE' or struct.unpack_from('<I',data,4)[0]!=len(data)-8:
            raise SoundError('Keine vollständige RIFF-WAV-Datei.')
        try:
            with wave.open(io.BytesIO(data)) as w:
                channels,rate,frames=w.getnchannels(),w.getframerate(),w.getnframes()
                if w.getsampwidth()!=2 or w.getcomptype()!='NONE':raise SoundError('WAV muss 16-Bit-PCM sein. Im Browser umwandeln.')
                if len(w.readframes(frames))!=frames*channels*2:raise SoundError('WAV-Daten abgeschnitten.')
        except (wave.Error,EOFError) as exc:raise SoundError('WAV-Format nicht unterstützt.') from exc
    elif extension=='.ogg':
        pos=0;sequence=0;serial=None;first=bytearray();packet_done=False;frames=-1;ended=False
        while pos<len(data):
            if ended or data[pos:pos+5]!=b'OggS\x00' or pos+27>len(data):raise SoundError('Ungültiger Ogg-Container.')
            n=data[pos+26];table=data[pos+27:pos+27+n]
            if len(table)!=n:raise SoundError('Ogg-Seitentabelle abgeschnitten.')
            size=27+n+sum(table);page=bytearray(data[pos:pos+size])
            if len(page)!=size:raise SoundError('Ogg-Seite abgeschnitten.')
            flag=page[5];current_serial,current_seq,crc=struct.unpack_from('<III',page,14)
            if serial is None:
                serial=current_serial
                if not flag&2 or flag&1:raise SoundError('Ogg-Startseite fehlt.')
            elif flag&2:raise SoundError('Mehrere Ogg-Streams werden nicht unterstützt.')
            if current_serial!=serial or current_seq!=sequence:raise SoundError('Ogg-Seitenfolge beschädigt.')
            page[22:26]=b'\0'*4
            if ogg_crc(page)!=crc:raise SoundError('Ogg-Prüfsumme stimmt nicht.')
            offset=27+n
            for length in table:
                if not packet_done:
                    first.extend(page[offset:offset+length])
                    if len(first)>4096:raise SoundError('Ogg-Header zu groß.')
                    if length<255:packet_done=True
                offset+=length
            frames=struct.unpack_from('<q',page,6)[0];ended=bool(flag&4)
            pos+=size;sequence+=1
        if not ended or len(first)<30 or first[:7]!=b'\x01vorbis' or not first[29]&1:
            raise SoundError('Ogg-Vorbis benötigt. Opus/OGA bitte vorab in WAV oder Vorbis umwandeln.')
        if struct.unpack_from('<I',first,7)[0]!=0:raise SoundError('Unbekannte Vorbis-Version.')
        channels,rate=first[11],struct.unpack_from('<I',first,12)[0]
    else:raise SoundError('Ersetzen wird für .wav und .ogg (Vorbis) unterstützt.')
    if channels not in (1,2) or not 8000<=rate<=96000 or not 0<frames<=rate*15:
        raise SoundError('Kurzer Effekt erforderlich: 1–2 Kanäle, 8–96 kHz, maximal 15 Sekunden.')
    return {'format':extension[1:],'channels':channels,'rate':rate,'duration':round(frames/rate,3),'bytes':len(data)}


class WadIndex:
    def __init__(self,path):
        self.path=Path(path);self.entries={};total=self.path.stat().st_size
        if total>0x7fffffff:raise SoundError('Archive über 2 GB werden noch nicht bearbeitet.')
        with self.path.open('rb') as f:
            if f.read(5)!=b'KIWAD':raise SoundError('Kein KIWAD-Archiv.')
            header=f.read(8)
            if len(header)!=8:raise SoundError('Archivheader abgeschnitten.')
            version,count=struct.unpack('<ll',header)
            if version not in (1,2) or not 0<=count<=200000:raise SoundError('Unbekannte KIWAD-Version oder ungültige Dateianzahl.')
            if version==2 and len(f.read(1))!=1:raise SoundError('Archivheader abgeschnitten.')
            spans=[]
            for _ in range(count):
                at=f.tell();raw=f.read(RECORD.size)
                if len(raw)!=RECORD.size:raise SoundError('Dateitabelle abgeschnitten.')
                offset,size,zsize,compressed,crc,n=RECORD.unpack(raw)
                if raw[12] not in (0,1) or not 1<=n<=4096 or size<0:raise SoundError('Ungültiger Archiveintrag.')
                name=f.read(n)
                if len(name)!=n or name[-1:]!=b'\0' or b'\0' in name[:-1]:raise SoundError('Ungültiger Archivname.')
                try:name=name[:-1].decode('utf-8')
                except UnicodeDecodeError as exc:raise SoundError('Ungültiger Archivname.') from exc
                length=zsize if compressed else size
                if name in self.entries or length<0 or offset<0 or offset+length>total:raise SoundError('Ungültige Archivgrenzen oder doppelte Namen.')
                self.entries[name]={'at':at,'raw':raw,'offset':offset,'size':size,'length':length,'compressed':compressed,'crc':crc}
                if length:spans.append((offset,offset+length))
            end=f.tell();spans.sort()
            last=end
            for start,stop in spans:
                if start<last:raise SoundError('Überlappende Archivdaten werden nicht verändert.')
                last=stop

    def read(self,name):
        entry=self.entries.get(name)
        if not entry:raise SoundError('Sound nicht im Archiv gefunden. Liste neu laden.')
        if entry['size']>MAX_AUDIO or entry['length']>MAX_AUDIO:raise SoundError('Sound zu groß für kurze Effekte (3 MB).')
        with self.path.open('rb') as f:f.seek(entry['offset']);stored=f.read(entry['length'])
        if stored[:4]==b'\0'*4:raise SoundError('Sound ist noch nicht vollständig vom Spiel heruntergeladen.')
        if ki_crc(stored)!=entry['crc']:raise SoundError('Original-Prüfsumme unbekannt oder beschädigt. Kein Austausch möglich.')
        if entry['compressed']:
            try:
                obj=zlib.decompressobj();data=obj.decompress(stored,MAX_AUDIO+1)
                if not obj.eof or obj.unconsumed_tail or obj.unused_data:raise SoundError('Ungültige komprimierte Sounddaten.')
            except zlib.error as exc:raise SoundError('Sounddaten nicht lesbar.') from exc
        else:data=stored
        if len(data)!=entry['size']:raise SoundError('Soundgröße stimmt nicht.')
        return data


def installation(value):
    if not isinstance(value,str) or len(value)>512:raise SoundError('Installationsordner wählen.')
    p=Path(value)
    if not p.is_absolute() or value.startswith(('\\\\','//')):raise SoundError('Lokalen, absoluten Wizard101-Installationsordner wählen.')
    p=p.resolve();game=p/'Data'/'GameData'
    if not (p/'Bin'/'WizardGraphicalClient.exe').is_file() or not game.is_dir():raise SoundError('Bin/WizardGraphicalClient.exe oder Data/GameData fehlt.')
    if game.resolve()!=game or str(p).startswith(('\\\\','//')):raise SoundError('Umgeleitete/Netzwerk-Spielordner werden nicht verändert.')
    return p


class SoundStore:
    def __init__(self,root,guard):
        self.root=Path(root);self.guard=guard;self.game=None
        self.config=self.root/'settings.json'
        if self.config.exists():
            try:self.game=installation(json.loads(self.config.read_text(encoding='utf-8'))['installation'])
            except (ValueError,KeyError,OSError):pass

    def configure(self,path):
        self.game=installation(path);self.root.mkdir(parents=True,exist_ok=True)
        json_save(self.config,{'installation':str(self.game)})
        return self.archives()

    def archives(self):
        if not self.game:return {'installation':'','archives':[]}
        self.game=installation(str(self.game))
        rows=[{'id':p.name,'bytes':p.stat().st_size} for p in (self.game/'Data'/'GameData').glob('*.wad') if not p.is_symlink()]
        rows.sort(key=lambda r:(not ('sound' in r['id'].lower()),r['id'].lower()))
        return {'installation':str(self.game),'archives':rows[:4096]}

    def path(self,archive):
        if not self.game:raise SoundError('Zuerst Installation auswählen.')
        installation(str(self.game))
        if not isinstance(archive,str) or not archive.lower().endswith('.wad') or any(c in archive for c in '/\\:') or archive in ('.','..'):raise SoundError('Ungültiges Archiv.')
        p=self.game/'Data'/'GameData'/archive
        if not p.is_file() or p.resolve()!=p:raise SoundError('Archiv fehlt oder ist umgeleitet.')
        return p

    def folder(self,path):
        key=hashlib.sha256(str(Path(path).resolve()).casefold().encode()).hexdigest()
        return self.root/'backups'/key

    def state(self,path,check=False):
        folder=self.folder(path);journal=folder/'journal.json'
        if not journal.exists():return None
        s=json.loads(journal.read_text(encoding='utf-8'))
        if s.get('archive')!=str(path) or s.get('schema')!=1:raise SoundError('Sicherungsjournal stimmt nicht zum Archiv.')
        if check or s.get('pending'):
            now=digest(path)
            if s.get('pending'):
                tx=s['pending']
                if now==tx['after']:s.update(expected=tx['after'],changes=tx['changes'])
                elif now!=s['expected']:raise SoundError('Archiv nach unterbrochenem Vorgang verändert. Sicherung behalten und Installation prüfen.')
                s.pop('pending');json_save(journal,s)
            if now!=s['expected']:raise SoundError('Archiv wurde außerhalb der Sound-Zentrale verändert (z. B. Update). Kein automatisches Überschreiben mit alter Sicherung.')
        return s

    def files(self,archive,query='',offset=0):
        path=self.path(archive);index=WadIndex(path);state=self.state(path)
        if not isinstance(query,str) or len(query)>150 or type(offset) is not int or not 0<=offset<=200000:raise SoundError('Suche ungültig.')
        changes=(state or {}).get('changes',{});rows=sound_rows(index,changes,query)
        return {'files':rows[offset:offset+120],'total':len(rows),'offset':offset,'changes':len(changes),'backup':str(self.folder(path)) if state else None}

    def search(self,query='',progress=lambda s:None):
        if not isinstance(query,str) or len(query)>150:raise SoundError('Suche ungültig.')
        archives=self.archives()['archives']
        if not self.game:raise SoundError('Zuerst Installation auswählen.')
        matches=[];total=0;errors=[];failed=0
        for i,archive in enumerate(archives):
            progress(f"Sound-Suche: Archiv {i+1}/{len(archives)} · {archive['id']}")
            try:
                path=self.path(archive['id']);index=WadIndex(path);saved=self.state(path)
                rows=sound_rows(index,(saved or {}).get('changes',{}),query)
                # With no query, only name hints are shown, never guessed game events.
                if not query:rows=[row for row in rows if row['candidate']]
                total+=len(rows)
                if len(matches)<120:
                    matches.extend({**row,'archive':archive['id']} for row in rows[:120-len(matches)])
            except (SoundError,OSError,ValueError,KeyError) as exc:
                failed+=1
                if len(errors)<8:errors.append({'archive':archive['id'],'message':str(exc)[:180]})
        return {'files':matches,'total':total,'archives':len(archives),'failed':failed,'errors':errors,'query':query,'limited':total>120}

    def changes(self):
        rows=[];errors=[]
        for archive in self.archives()['archives']:
            path=self.path(archive['id'])
            try:
                saved=self.state(path)
                for name,change in (saved or {}).get('changes',{}).items():
                    if len(rows)<500:rows.append({'archive':archive['id'],'name':name,'label':change.get('label',''),
                                                 'backup':str(self.folder(path))})
            except (SoundError,OSError,ValueError,KeyError) as exc:
                if len(errors)<8:errors.append({'archive':archive['id'],'message':str(exc)[:180]})
        return {'changes':rows,'errors':errors,'limited':len(rows)>=500}

    def inspect(self,archive,name):
        path=self.path(archive);data=WadIndex(path).read(name);info=audio_info(data,Path(name).suffix.lower())
        result={**info,'sha256':hashlib.sha256(data).hexdigest(),'data':base64.b64encode(data).decode()}
        saved=self.state(path)
        if name in (saved or {}).get('changes',{}):
            source=WadIndex(self.folder(path)/'original.wad').read(name)
            result['baseline']={**audio_info(source,Path(name).suffix.lower()),'data':base64.b64encode(source).decode()}
        return result

    def replace(self,archive,name,data,expected,label='',restore=False,progress=lambda s:None):
        self.guard();path=self.path(archive);index=WadIndex(path)
        if name not in index.entries:raise SoundError('Sound nicht gefunden.')
        if Path(name).suffix.lower() not in ('.wav','.ogg'):raise SoundError('Nur WAV oder Vorbis ersetzen.')
        current=index.read(name)
        if hashlib.sha256(current).hexdigest()!=expected:raise SoundError('Sound seit der Vorschau verändert. Erneut auswählen.')
        if not restore:audio_info(current,Path(name).suffix.lower());audio_info(data,Path(name).suffix.lower())
        progress('Archiv und Sicherung prüfen …');before=digest(path);s=self.state(path,True)
        folder=self.folder(path);backup=folder/'original.wad';journal=folder/'journal.json'
        if not s:
            if restore:raise SoundError('Kein Original für diesen Sound gesichert.')
            folder.mkdir(parents=True,exist_ok=True)
            if backup.exists():raise SoundError('Sicherung ohne Journal vorhanden. Vorhandene Sicherung zuerst prüfen.')
            if shutil.disk_usage(folder).free<path.stat().st_size+32*1024*1024:raise SoundError('Zu wenig Platz für die Originalsicherung.')
            progress('Originalarchiv lokal sichern …');part=folder/'original.part'
            try:
                shutil.copy2(path,part)
                if digest(part)!=before:raise SoundError('Archiv während Sicherung verändert.')
                with part.open('r+b') as f:os.fsync(f.fileno())
                os.replace(part,backup)
            finally:part.unlink(missing_ok=True)
            s={'schema':1,'archive':str(path),'baseline':before,'expected':before,'changes':{}}
            json_save(journal,s)
        if before!=s['expected'] or digest(backup)!=s['baseline']:raise SoundError('Archiv oder Originalsicherung verändert. Vorgang abgebrochen.')
        changes=dict(s['changes']);original_index=WadIndex(backup)
        if name not in original_index.entries:raise SoundError('Sound fehlt in der Sicherung.')
        if restore:
            if name not in changes:raise SoundError('Dieser Sound wurde nicht geändert.')
            changes.pop(name)
        else:changes[name]={'label':str(label)[:100],'sha256':hashlib.sha256(data).hexdigest()}
        if shutil.disk_usage(path.parent).free<path.stat().st_size+len(data)+32*1024*1024:raise SoundError('Zu wenig Platz für eine geprüfte Archivkopie.')
        progress('Einzelnen Sound in Arbeitskopie ändern …')
        fd,tempname=tempfile.mkstemp(prefix='.mythic-sound-',suffix='.tmp',dir=path.parent);os.close(fd);tmp=Path(tempname)
        try:
            shutil.copy2(backup if restore and not changes else path,tmp)
            if restore and not changes:
                with tmp.open('r+b') as f:os.fsync(f.fileno())
            if not (restore and not changes):
                with tmp.open('r+b') as f:
                    if restore:raw=original_index.entries[name]['raw']
                    else:
                        f.seek(0,2);offset=f.tell()
                        if offset+len(data)>0x7fffffff:raise SoundError('Archiv würde 2 GB überschreiten.')
                        f.write(data);raw=RECORD.pack(offset,len(data),-1,False,ki_crc(data),RECORD.unpack(index.entries[name]['raw'])[-1])
                    f.seek(index.entries[name]['at']);f.write(raw);f.flush();os.fsync(f.fileno())
            verify=WadIndex(tmp);wanted=original_index.read(name) if restore else data
            if verify.read(name)!=wanted:raise SoundError('Prüfung der neuen Sounddaten fehlgeschlagen.')
            progress('Prüfsummen bestätigen …');after=digest(tmp)
            if restore and not changes and after!=s['baseline']:raise SoundError('Wiederherstellung stimmt nicht mit Original überein.')
            if digest(path)!=before:raise SoundError('Archiv wurde während der Änderung extern verändert.')
            self.guard()
            # Write-ahead journal: recover both sides of an interrupted atomic replace.
            s['pending']={'after':after,'changes':changes};json_save(journal,s)
            os.replace(tmp,path)
            s.update(expected=after,changes=changes);s.pop('pending');json_save(journal,s)
            return {'changed':not restore,'name':name,'backup':str(folder),'archive':archive}
        finally:tmp.unlink(missing_ok=True)
