package com.example.labelAI.service;

import com.example.labelAI.domain.User;
import com.example.labelAI.utils.Result;

import java.util.List;
import java.util.Map;


public interface UserService {
    List<User> getUsers();

    Result<Map<String,String>> login(String input,String password);

    String logout(String token);

    String registerUser(User user);
    String checkEmail(String email);
    String checkName(String name);
}
