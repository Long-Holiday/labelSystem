package com.example.rmhospital.service;

import com.example.rmhospital.domain.User;
import com.example.rmhospital.utils.Result;

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
