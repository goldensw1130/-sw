package com.oreummok.nativeapp;
final class ApiKeyInput {
 static String normalize(String raw){String v=raw==null?"":raw;if(v.length()>4096)throw new IllegalArgumentException("복사한 내용이 너무 깁니다. API 키만 복사해 주세요.");v=v.replaceAll("[\\s\\u00a0\\u200b-\\u200f\\u202a-\\u202e\\u2060-\\u2069\\ufeff]","").replaceFirst("(?i)^(GEMINI_API_KEY|GOOGLE_API_KEY|API_KEY)=","");if(v.length()>1){char a=v.charAt(0),z=v.charAt(v.length()-1);if((a=='\"'&&z=='\"')||(a=='\''&&z=='\'')||(a=='`'&&z=='`')||(a=='“'&&z=='”')||(a=='‘'&&z=='’'))v=v.substring(1,v.length()-1);}if(v.length()<20||v.length()>512||!v.matches("[\\x21-\\x7e]+")||v.indexOf('"')>=0||v.indexOf('\'')>=0||v.indexOf('`')>=0)throw new IllegalArgumentException("API 키만 붙여넣어 주세요. 한글·설명 문구 또는 잘린 키가 포함되어 있는지 확인하세요.");return v;}
}
