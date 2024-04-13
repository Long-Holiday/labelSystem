package com.example.labelAI.utils;

import java.security.SecureRandom;
/**
  * @description:生成强密码工具类
  * @author: lf
  * @date:2023/12/3
 */
public class PasswordGenerator {
    private static final String CHAR_LOWER = "abcdefghijklmnopqrstuvwxyz";
    private static final String CHAR_UPPER = CHAR_LOWER.toUpperCase();
    private static final String NUMBER = "0123456789";
    private static final String OTHER_CHAR = "!@#$%&*()_+-=[]?";
    private static final String PASSWORD_ALLOW = CHAR_LOWER + CHAR_UPPER + NUMBER + OTHER_CHAR;
    private static SecureRandom random = new SecureRandom();

    public static String generate(int length) {
        if (length < 1) throw new IllegalArgumentException();

        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            int rndCharAt = random.nextInt(PASSWORD_ALLOW.length());
            char rndChar = PASSWORD_ALLOW.charAt(rndCharAt);
            sb.append(rndChar);
        }

        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println("------------------------------------------------------------------------");
        System.out.println("强密码为: " + generate(20));
        System.out.println("------------------------------------------------------------------------");
    }
}
