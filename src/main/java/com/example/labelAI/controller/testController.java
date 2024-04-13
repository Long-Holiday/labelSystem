package com.example.labelAI.controller;

import com.example.labelAI.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class testController {
    @Autowired
    private UserService userService;

    @GetMapping("/hello")
    public String hello() {
        return "hello security";
    }
    @GetMapping("/admin/hello")
    public String adminHello() {
        return "hello admin security";
    }




}
