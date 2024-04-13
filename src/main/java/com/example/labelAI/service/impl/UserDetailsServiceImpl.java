package com.example.labelAI.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.labelAI.domain.User;
import com.example.labelAI.mapper.UserMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class UserDetailsServiceImpl implements UserDetailsService {
    @Autowired
    private UserMapper userMapper;

    /**
     * @description:重写查询用户方法，查内存中的用户--->去查数据库中的用户表进行验证，封装UserDetails对象返回
     * @date:2023/12/2
     */
    @Override
    public UserDetails loadUserByUsername(String input) throws UsernameNotFoundException {
        LambdaQueryWrapper<User> queryWrapper = new LambdaQueryWrapper<User>();
        queryWrapper.eq(User::getEmail, input);
        User user = userMapper.selectOne(queryWrapper);
        if (user == null) {
            queryWrapper = new LambdaQueryWrapper<User>();
            queryWrapper.eq(User::getUserName, input);
            user = userMapper.selectOne(queryWrapper);
            if (user == null) {
                throw new UsernameNotFoundException("用户名或邮箱不存在");
            }
        }
//        //定义权限列表.角色（管理员，用户）----权限（读写）
//        List<GrantedAuthority> authorities = new ArrayList<>();
//        // 用户可以访问的资源名称（或者说用户所拥有的权限） 注意：必须"ROLE_"开头
//        if (user.getRole()!=null){
//            authorities.add(new SimpleGrantedAuthority(user.getRole().getKeyWord()));
//            if (user.getRole().getPermissionList() !=null && user.getRole().getPermissionList().size()>0){
//                for (Permission permission : user.getRole().getPermissionList()) {
//                    authorities.add(new SimpleGrantedAuthority(permission.getKeyWord()));
//                }
//            }
//        }
//定义权限列表.角色（管理员，用户）
        List<GrantedAuthority> authorities = new ArrayList<>();
        // 用户可以访问的资源名称（或者说用户所拥有的权限） 注意：必须"ROLE_"开头
        if (user.getRole() != null) {
            authorities.add(new SimpleGrantedAuthority("ROLE_" + user.getRole()));
        }
        org.springframework.security.core.userdetails.User user1 = new org.springframework.security.core.userdetails.User(user.getEmail(), user.getPassword(), authorities);
        return user1;
    }

}
