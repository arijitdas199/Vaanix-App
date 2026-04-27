import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View, StyleSheet, TextInput, TouchableOpacity, FlatList, KeyboardAvoidingView, Platform, ActivityIndicator, Image, Modal, Pressable,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { Audio } from "expo-av";
import { Text } from "../../src/components/Text";
import { Avatar } from "../../src/components/Avatar";
import { useTheme } from "../../src/lib/theme";
import { useAuth } from "../../src/lib/auth";
import { api } from "../../src/lib/api";
import { useWS } from "../../src/lib/ws";

const REACTIONS = ["❤️", "👍", "😂", "😮", "😢", "🔥"];

function timeFmt(iso?: string) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return ""; }
}

export default function ChatScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = String(params.id);
  const { c } = useTheme();
  const { user } = useAuth();
  const router = useRouter();
  const [conv, setConv] = useState<any>(null);
  const [msgs, setMsgs] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [typingFrom, setTypingFrom] = useState<string | null>(null);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [showActions, setShowActions] = useState<{ msg: any } | null>(null);
  const [replyTo, setReplyTo] = useState<any | null>(null);
  const listRef = useRef<FlatList>(null);
  const typingTimeoutRef = useRef<any>(null);

  const peer = useMemo(() => conv?.type === "direct" ? conv.participants.find((p: any) => p.id !== user?.id) : null, [conv, user?.id]);
  const title = conv?.type === "group" ? conv.name : peer?.display_name || "Chat";

  const load = useCallback(async () => {
    try {
      const [cd, m] = await Promise.all([api.getConv(id), api.listMessages(id)]);
      setConv(cd); setMsgs(m || []);
    } catch {}
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const { send: wsSend } = useWS((msg) => {
    if (msg.type === "new_message" && msg.conversation_id === id) {
      setMsgs((prev) => prev.find((p) => p.id === msg.message.id) ? prev : [...prev, msg.message]);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
      // mark read
      api.listMessages(id).catch(() => {});
    } else if (msg.type === "message_updated") {
      setMsgs((prev) => prev.map((p) => p.id === msg.message.id ? msg.message : p));
    } else if (msg.type === "message_deleted") {
      setMsgs((prev) => prev.map((p) => p.id === msg.message_id ? { ...p, deleted_for_all: true, content: "" } : p));
    } else if (msg.type === "typing" && msg.conversation_id === id && msg.user_id !== user?.id) {
      setTypingFrom(msg.is_typing ? msg.user_id : null);
    } else if (msg.type === "presence" || msg.type === "read_receipt") {
      load();
    }
  });

  const onChangeText = (v: string) => {
    setText(v);
    wsSend({ type: "typing", conversation_id: id, is_typing: true });
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => wsSend({ type: "typing", conversation_id: id, is_typing: false }), 1500);
  };

  const sendText = async () => {
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      await api.sendMessage(id, { type: "text", content: text.trim(), reply_to: replyTo?.id });
      setText(""); setReplyTo(null);
    } catch {} finally { setSending(false); }
  };

  const pickImage = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.All, base64: true, quality: 0.6 });
    if (r.canceled || !r.assets?.[0]) return;
    const asset = r.assets[0];
    const data = `data:${asset.mimeType || "image/jpeg"};base64,${asset.base64}`;
    const isVideo = (asset.mimeType || "").startsWith("video") || asset.type === "video";
    await api.sendMessage(id, { type: isVideo ? "video" : "image", content: data, mime_type: asset.mimeType, reply_to: replyTo?.id });
    setReplyTo(null);
  };

  const pickDoc = async () => {
    const r = await DocumentPicker.getDocumentAsync({ type: "*/*", copyToCacheDirectory: true });
    if (r.canceled || !r.assets?.[0]) return;
    const a = r.assets[0];
    try {
      const resp = await fetch(a.uri);
      const blob = await resp.blob();
      const reader: any = new FileReader();
      reader.onloadend = async () => {
        await api.sendMessage(id, { type: "document", content: reader.result, file_name: a.name, mime_type: a.mimeType, reply_to: replyTo?.id });
        setReplyTo(null);
      };
      reader.readAsDataURL(blob);
    } catch {}
  };

  const startRecording = async () => {
    try {
      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording: rec } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      setRecording(rec);
    } catch {}
  };

  const stopRecording = async () => {
    if (!recording) return;
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      const status: any = await recording.getStatusAsync();
      setRecording(null);
      if (!uri) return;
      const resp = await fetch(uri);
      const blob = await resp.blob();
      const reader: any = new FileReader();
      reader.onloadend = async () => {
        await api.sendMessage(id, { type: "voice", content: reader.result, mime_type: "audio/m4a", duration: status?.durationMillis ? status.durationMillis / 1000 : 0 });
      };
      reader.readAsDataURL(blob);
    } catch { setRecording(null); }
  };

  const playVoice = async (uri: string) => {
    try {
      const { sound } = await Audio.Sound.createAsync({ uri });
      await sound.playAsync();
    } catch {}
  };

  const renderItem = ({ item }: any) => {
    const mine = item.sender_id === user?.id;
    const replied = item.reply_to ? msgs.find((m) => m.id === item.reply_to) : null;
    const myReact = item.reactions?.find((r: any) => r.user_id === user?.id);
    return (
      <Pressable onLongPress={() => setShowActions({ msg: item })} style={[styles.bubbleWrap, mine ? styles.right : styles.left]}>
        {!mine && conv?.type === "group" ? <Text variant="small" color={c.textTertiary} style={{ marginBottom: 2, marginLeft: 8 }}>{item.sender_name}</Text> : null}
        <View style={[styles.bubble, mine ? { backgroundColor: c.bubbleSent, borderBottomRightRadius: 6 } : { backgroundColor: c.bubbleReceived, borderBottomLeftRadius: 6 }]}>
          {replied ? (
            <View style={[styles.reply, { borderLeftColor: mine ? "#fff" : c.primary }]}>
              <Text variant="small" color={mine ? "#E0E7FF" : c.primary} style={{ fontWeight: "700" }}>{replied.sender_id === user?.id ? "You" : replied.sender_name}</Text>
              <Text variant="small" color={mine ? "#E0E7FF" : c.textSecondary} numberOfLines={1}>{replied.type === "text" ? replied.content : `[${replied.type}]`}</Text>
            </View>
          ) : null}
          {item.deleted_for_all ? (
            <Text color={mine ? "#E0E7FF" : c.textTertiary} style={{ fontStyle: "italic" }}>🚫 This message was deleted</Text>
          ) : item.type === "text" ? (
            <Text color={mine ? c.bubbleTextSent : c.bubbleTextReceived}>{item.content}</Text>
          ) : item.type === "image" ? (
            <Image source={{ uri: item.content }} style={{ width: 220, height: 220, borderRadius: 14 }} resizeMode="cover" />
          ) : item.type === "video" ? (
            <View style={{ width: 220, height: 140, borderRadius: 14, backgroundColor: "#000", alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="videocam" size={36} color="#fff" />
              <Text color="#fff" variant="small" style={{ marginTop: 6 }}>Video</Text>
            </View>
          ) : item.type === "voice" ? (
            <TouchableOpacity onPress={() => playVoice(item.content)} style={{ flexDirection: "row", alignItems: "center", gap: 10, minWidth: 160 }}>
              <Ionicons name="play-circle" size={32} color={mine ? "#fff" : c.primary} />
              <Text color={mine ? "#fff" : c.textPrimary}>Voice note {item.duration ? `· ${Math.round(item.duration)}s` : ""}</Text>
            </TouchableOpacity>
          ) : item.type === "document" ? (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10, minWidth: 200 }}>
              <Ionicons name="document" size={28} color={mine ? "#fff" : c.primary} />
              <Text color={mine ? "#fff" : c.textPrimary} numberOfLines={1} style={{ flex: 1 }}>{item.file_name || "Document"}</Text>
            </View>
          ) : null}
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4, alignSelf: mine ? "flex-end" : "flex-start" }}>
            <Text variant="small" color={mine ? "#E0E7FF" : c.textTertiary} style={{ fontSize: 10 }}>{timeFmt(item.created_at)}</Text>
            {mine ? (
              <Ionicons name={item.read_by?.length > 1 ? "checkmark-done" : "checkmark"} size={14} color={item.read_by?.length > 1 ? "#7DD3FC" : "#E0E7FF"} />
            ) : null}
          </View>
        </View>
        {item.reactions?.length ? (
          <View style={[styles.reacts, mine ? { right: 8 } : { left: 8 }, { backgroundColor: c.surface, borderColor: c.border }]}>
            {Array.from(new Set(item.reactions.map((r: any) => r.emoji))).map((e: any) => (
              <Text key={e} style={{ fontSize: 13 }}>{e}</Text>
            ))}
            <Text variant="small" color={c.textTertiary} style={{ marginLeft: 2 }}>{item.reactions.length}</Text>
          </View>
        ) : null}
      </Pressable>
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={[styles.header, { borderBottomColor: c.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 6 }}>
          <Ionicons name="chevron-back" size={26} color={c.textPrimary} />
        </TouchableOpacity>
        <Avatar name={title} uri={conv?.type === "group" ? conv.avatar : peer?.avatar} size={40} online={conv?.type === "direct" ? !!peer?.online : false} />
        <View style={{ flex: 1, marginLeft: 10 }}>
          <Text style={{ fontWeight: "700" }} numberOfLines={1}>{title}</Text>
          <Text variant="small" color={typingFrom ? c.primary : c.textTertiary} numberOfLines={1}>
            {typingFrom ? "typing…" : conv?.type === "group" ? `${conv.participants?.length || 0} members` : peer?.online ? "online" : "offline"}
          </Text>
        </View>
        <TouchableOpacity onPress={() => router.push({ pathname: "/conv-info", params: { id } })}>
          <Ionicons name="ellipsis-vertical" size={22} color={c.textPrimary} />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}>
        <FlatList
          ref={listRef}
          data={msgs}
          keyExtractor={(it) => it.id}
          renderItem={renderItem}
          contentContainerStyle={{ padding: 12, paddingBottom: 20 }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
          testID="messages-list"
        />

        {replyTo ? (
          <View style={[styles.replyBar, { backgroundColor: c.surfaceVariant, borderColor: c.border }]}>
            <View style={{ flex: 1 }}>
              <Text variant="small" color={c.primary} style={{ fontWeight: "700" }}>Replying to {replyTo.sender_id === user?.id ? "yourself" : replyTo.sender_name}</Text>
              <Text variant="small" color={c.textSecondary} numberOfLines={1}>{replyTo.type === "text" ? replyTo.content : `[${replyTo.type}]`}</Text>
            </View>
            <TouchableOpacity onPress={() => setReplyTo(null)}><Ionicons name="close" size={18} color={c.textSecondary} /></TouchableOpacity>
          </View>
        ) : null}

        <View style={[styles.inputBar, { backgroundColor: c.surface, borderTopColor: c.border }]}>
          <TouchableOpacity testID="attach-doc" onPress={pickDoc} style={styles.iconBtn}><Ionicons name="attach" size={22} color={c.textSecondary} /></TouchableOpacity>
          <TouchableOpacity testID="attach-image" onPress={pickImage} style={styles.iconBtn}><Ionicons name="image-outline" size={22} color={c.textSecondary} /></TouchableOpacity>
          <View style={[styles.field, { backgroundColor: c.surfaceVariant }]}>
            <TextInput
              testID="message-input"
              value={text}
              onChangeText={onChangeText}
              placeholder="Type a message…"
              placeholderTextColor={c.textTertiary}
              style={{ flex: 1, color: c.textPrimary, fontSize: 15, paddingVertical: 8 }}
              multiline
            />
          </View>
          {text.trim().length ? (
            <TouchableOpacity testID="send-btn" onPress={sendText} disabled={sending}>
              <LinearGradient colors={c.gradient as any} style={styles.sendBtn}>
                {sending ? <ActivityIndicator color="#fff" size="small" /> : <Ionicons name="send" size={18} color="#fff" />}
              </LinearGradient>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity testID="voice-btn" onPressIn={startRecording} onPressOut={stopRecording} style={styles.iconBtn}>
              <Ionicons name={recording ? "radio-button-on" : "mic"} size={24} color={recording ? c.error : c.primary} />
            </TouchableOpacity>
          )}
        </View>
      </KeyboardAvoidingView>

      {/* Actions modal */}
      <Modal visible={!!showActions} transparent animationType="fade" onRequestClose={() => setShowActions(null)}>
        <Pressable style={{ flex: 1, backgroundColor: c.overlay, justifyContent: "flex-end" }} onPress={() => setShowActions(null)}>
          <Pressable onPress={() => {}} style={[styles.sheet, { backgroundColor: c.surface }]}>
            <View style={{ flexDirection: "row", justifyContent: "space-around", paddingVertical: 6 }}>
              {REACTIONS.map((e) => (
                <TouchableOpacity key={e} onPress={async () => { if (showActions) { await api.react(showActions.msg.id, e); setShowActions(null); } }}>
                  <Text style={{ fontSize: 26 }}>{e}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={{ height: 1, backgroundColor: c.border, marginVertical: 6 }} />
            <SheetItem icon="arrow-undo-outline" label="Reply" onPress={() => { setReplyTo(showActions?.msg); setShowActions(null); }} />
            <SheetItem icon="star-outline" label="Star" onPress={async () => { if (showActions) { await api.star(showActions.msg.id); setShowActions(null); } }} />
            {showActions?.msg.sender_id === user?.id ? (
              <SheetItem icon="trash-outline" danger label="Delete for everyone" onPress={async () => { if (showActions) { await api.deleteMessage(showActions.msg.id, true); setShowActions(null); } }} />
            ) : null}
            <SheetItem icon="trash-bin-outline" label="Delete for me" onPress={async () => { if (showActions) { await api.deleteMessage(showActions.msg.id, false); setMsgs((p) => p.filter((m) => m.id !== showActions.msg.id)); setShowActions(null); } }} />
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function SheetItem({ icon, label, onPress, danger }: any) {
  const { c } = useTheme();
  return (
    <TouchableOpacity onPress={onPress} style={{ flexDirection: "row", alignItems: "center", padding: 14, gap: 12 }}>
      <Ionicons name={icon} size={20} color={danger ? c.error : c.textSecondary} />
      <Text color={danger ? c.error : undefined} style={{ fontWeight: "600" }}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingBottom: 8, gap: 6, borderBottomWidth: StyleSheet.hairlineWidth },
  bubbleWrap: { marginVertical: 4, maxWidth: "82%" },
  left: { alignSelf: "flex-start" },
  right: { alignSelf: "flex-end" },
  bubble: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 22, minWidth: 60 },
  reply: { borderLeftWidth: 3, paddingLeft: 8, paddingVertical: 4, marginBottom: 6, borderRadius: 4 },
  reacts: { position: "absolute", bottom: -10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 12, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 2 },
  inputBar: { flexDirection: "row", alignItems: "flex-end", padding: 8, gap: 6, borderTopWidth: StyleSheet.hairlineWidth },
  iconBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  field: { flex: 1, borderRadius: 22, paddingHorizontal: 14, minHeight: 42, justifyContent: "center" },
  sendBtn: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
  replyBar: { flexDirection: "row", alignItems: "center", gap: 10, padding: 10, marginHorizontal: 8, borderRadius: 10, borderWidth: 1 },
  sheet: { padding: 12, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingBottom: 30 },
});
