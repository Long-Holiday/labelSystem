package com.example.rmhospital.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.rmhospital.domain.User;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.springframework.stereotype.Repository;

@Mapper
@Repository
public interface UserMapper extends BaseMapper<User> {
//    @Select("SELECT id FROM sys_user WHERE email = #{email}")
//    Integer getUserId(String email);

    @Insert("INSERT INTO sys_user (user_name, password, email, phone_number, sex, avatar, create_time, role) VALUES (#{userName}, #{password}, #{email}, #{phoneNumber}, #{sex}, #{avatar}, #{createTime}, #{role})")
    void insertUser(User user);
    @Select("SELECT COUNT(*) FROM sys_user WHERE email = #{email}")
    int countByEmail(String email);
    @Select("SELECT COUNT(*) FROM sys_user WHERE name = #{name}")
    int countByName(String name);
}
